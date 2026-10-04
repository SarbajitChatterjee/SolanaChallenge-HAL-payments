import { createFileRoute } from "@tanstack/react-router";
import {
  Bot,
  ChevronDown,
  History,
  KeyRound,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plus,
  TriangleAlert,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Panel } from "@/components/ab/Panel";
import { PillButton } from "@/components/ab/PillButton";
import { AgentForm } from "@/components/rules/AgentForm";
import { ItemForm } from "@/components/rules/ItemForm";
import { KeyDialog } from "@/components/rules/KeyDialog";
import { ConfirmDialog } from "@/components/rules/shared";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { api, type RuleAgent, type RuleItem, type RulesHistoryEntry } from "@/lib/api";
import { formatTime, formatUsdc, truncateAddress } from "@/lib/format";
import { useRefreshAll, useRules, useRulesHistory } from "@/lib/queries";
import { useSettings } from "@/lib/settings";
import { cn } from "@/lib/utils";

const TITLE = "Rules — HAL";
const DESCRIPTION =
  "Set who may buy what, how much, and when you get asked. Every change is recorded.";

export const Route = createFileRoute("/rules")({
  staticData: { sitemap: true },
  head: () => ({
    meta: [
      { title: TITLE },
      { name: "description", content: DESCRIPTION },
      { property: "og:title", content: TITLE },
      { property: "og:description", content: DESCRIPTION },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: RulesPage,
});

const actionLabel: Record<string, string> = {
  "agent.created": "Added agent",
  "agent.updated": "Changed agent",
  "agent.archived": "Archived agent",
  "agent.restored": "Restored agent",
  "item.created": "Added item",
  "item.updated": "Changed item",
  "item.archived": "Archived item",
  "item.restored": "Restored item",
  "demo.reset": "Reset the demo",
};

const fieldLabel: Record<string, string> = {
  per_task_cap: "Task budget",
  daily_cap: "Daily budget",
  approval_above: "Needs your OK above",
  allowed_tools: "May buy",
  description: "Description",
  price: "Agreed price",
  url: "Address",
  vendor: "Seller",
  name: "Name",
  active: "Active",
};

const ruleSections = [
  { id: "agents-heading", label: "Agents", icon: Bot },
  { id: "items-heading", label: "Items", icon: Package },
  { id: "history-heading", label: "History", icon: History },
] as const;

function showValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "–";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "–";
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

type Pending =
  | { kind: "agent"; agent: RuleAgent; active: boolean }
  | { kind: "item"; item: RuleItem; active: boolean }
  | null;

function RulesPage() {
  const { config, apiBaseUrl, openSettings } = useSettings();
  const rules = useRules();
  const history = useRulesHistory();
  const refreshAll = useRefreshAll();

  const [agentForm, setAgentForm] = useState<{ open: boolean; agent: RuleAgent | null }>({
    open: false,
    agent: null,
  });
  const [itemForm, setItemForm] = useState<{ open: boolean; item: RuleItem | null }>({
    open: false,
    item: null,
  });
  const [keyFor, setKeyFor] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [railCollapsed, setRailCollapsed] = useState(false);

  const items = rules.data?.items ?? [];
  const agents = rules.data?.agents ?? [];
  const itemName = useMemo(() => new Map(items.map((item) => [item.tool, item.name])), [items]);
  const activeAgents = agents.filter((agent) => agent.active);
  const archivedAgents = agents.filter((agent) => !agent.active);
  const hasToken = Boolean(config.token);

  async function applyPending() {
    if (!pending) return;
    if (pending.kind === "agent")
      await api.updateAgent(config, pending.agent.agent_id, { active: pending.active });
    else await api.updateItem(config, pending.item.tool, { active: pending.active });
    refreshAll();
  }

  const agentCard = (agent: RuleAgent) => (
    <Panel
      key={agent.agent_id}
      tone={agent.active ? "sky" : "white"}
      className={cn("flex min-h-full flex-col p-0 sm:p-0", !agent.active && "opacity-75")}
    >
      <div className="p-5 sm:p-6">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="panel-text font-display text-xl">{agent.agent_id}</h3>
          {agent.frozen ? (
            <span className="rounded-md border border-blocked-line bg-blocked-tint px-2 py-0.5 text-xs font-bold text-blocked-ink">
              Stopped
            </span>
          ) : null}
        </div>
        <p className="mt-1">{agent.description}</p>
        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          <span className="font-semibold">May buy:</span>
          {agent.allowed_tools.length === 0 ? (
            <span className="text-ink-muted">nothing yet</span>
          ) : null}
          {agent.allowed_tools.map((tool) => (
            <span key={tool} className="rounded-md border border-sky-line/35 bg-white px-2 py-1 text-sm">
              {itemName.get(tool) ?? tool}
            </span>
          ))}
        </div>
      </div>
      <dl className="mt-auto grid grid-cols-1 gap-2 px-5 sm:grid-cols-3 sm:px-6">
        {[
          ["Task budget", agent.per_task_cap],
          ["Daily budget", agent.daily_cap],
          ["Needs your OK above", agent.approval_above],
        ].map(([label, value]) => (
          <div key={label} className="panel-flat panel-sky min-w-0 px-3 py-3">
            <dt className="text-ink-muted text-xs font-semibold">{label}</dt>
            <dd className="nums mt-0.5 font-display text-base">{formatUsdc(value)}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap gap-2 p-5 sm:px-6">
        {agent.active ? (
          <PillButton className="bg-white" onClick={() => setAgentForm({ open: true, agent })}>
            <Pencil className="size-4" aria-hidden="true" />
            Edit
          </PillButton>
        ) : null}
        {hasToken ? (
          <PillButton className="bg-white" onClick={() => setKeyFor(agent.agent_id)}>
            <KeyRound className="size-4" aria-hidden="true" />
            Show key
          </PillButton>
        ) : null}
        {agent.active ? (
          <PillButton
            variant="destructive"
            onClick={() => setPending({ kind: "agent", agent, active: false })}
          >
            Archive
          </PillButton>
        ) : (
          <PillButton
            variant="primary"
            onClick={() => setPending({ kind: "agent", agent, active: true })}
          >
            Restore
          </PillButton>
        )}
      </div>
    </Panel>
  );

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="border-b-2 border-[var(--grid)] pb-7">
        <h1 className="font-display text-4xl">Rules</h1>
        <p className="text-ink-muted mt-2 max-w-3xl">
          Who may buy what, how much, and when you get asked. Changes apply to the next purchase and
          are recorded below.
        </p>
      </div>

      {!apiBaseUrl ? (
        <Panel tone="waiting" className="mt-5 flex flex-wrap items-center gap-3 py-3">
          <TriangleAlert className="panel-text size-5" aria-hidden="true" />
          <p className="panel-text font-semibold">
            Connect the API in Settings to see and change the rules.
          </p>
          <PillButton className="ml-auto bg-white" onClick={() => openSettings()}>
            Open Settings
          </PillButton>
        </Panel>
      ) : rules.isError ? (
        <Panel tone="blocked" className="mt-5 flex flex-wrap items-center gap-3 py-3">
          <TriangleAlert className="panel-text size-5" aria-hidden="true" />
          <p className="panel-text font-semibold">
            The browser can&apos;t load the rules from {apiBaseUrl}. Check Settings, then try again.
          </p>
          <PillButton className="ml-auto bg-white" onClick={() => void rules.refetch()}>
            Retry
          </PillButton>
        </Panel>
      ) : null}

      <nav className="mt-5 flex gap-2 overflow-x-auto md:hidden" aria-label="Rules sections">
        {ruleSections.map(({ id, label, icon: Icon }) => (
          <a key={id} href={`#${id}`} className="pill panel-white shrink-0 text-sm">
            <Icon className="size-4" aria-hidden="true" />
            {label}
          </a>
        ))}
      </nav>

      <div className={cn("mt-8 grid items-start gap-7", railCollapsed ? "md:grid-cols-[64px_1fr]" : "md:grid-cols-[190px_1fr]")}>
        <aside className="sticky top-24 hidden rounded-md border-2 border-[var(--grid)] bg-card p-2 md:block">
          <div className="mb-2 flex items-center justify-end border-b border-[var(--grid)] pb-2">
            <PillButton
              className="size-9 p-0"
              aria-label={railCollapsed ? "Expand section menu" : "Collapse section menu"}
              onClick={() => setRailCollapsed((value) => !value)}
            >
              {railCollapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
            </PillButton>
          </div>
          <nav className="space-y-1" aria-label="Rules sections">
            {ruleSections.map(({ id, label, icon: Icon }) => (
              <a
                key={id}
                href={`#${id}`}
                className="flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 font-semibold hover:bg-muted"
                title={railCollapsed ? String(label) : undefined}
              >
                <Icon className="size-4 shrink-0" aria-hidden="true" />
                {railCollapsed ? <span className="sr-only">{label}</span> : <span>{label}</span>}
              </a>
            ))}
          </nav>
        </aside>

        <div className="min-w-0">
      <section className="scroll-mt-28" aria-labelledby="agents-heading">
        <div className="flex flex-wrap items-center gap-3">
          <h2 id="agents-heading" className="font-display text-2xl">
            Agents
          </h2>
          <PillButton
            variant="primary"
            className="ml-auto"
            disabled={!rules.data}
            onClick={() => setAgentForm({ open: true, agent: null })}
          >
            <Plus className="size-4" aria-hidden="true" />
            Add agent
          </PillButton>
        </div>
        {rules.isLoading ? <p className="text-ink-muted mt-4">Loading the rules…</p> : null}
        <div className="mt-4 grid gap-5 xl:grid-cols-2">{activeAgents.map(agentCard)}</div>
        {archivedAgents.length > 0 ? (
          <div className="mt-4">
            <button
              type="button"
              className="flex items-center gap-2 rounded-lg px-2 py-1 font-semibold hover:bg-muted"
              aria-expanded={showArchived}
              onClick={() => setShowArchived((value) => !value)}
            >
              <ChevronDown
                className={cn("size-4 transition-transform", showArchived && "rotate-180")}
                aria-hidden="true"
              />
              Archived agents ({archivedAgents.length})
            </button>
            {showArchived ? (
              <div className="mt-3 grid gap-4 lg:grid-cols-2">{archivedAgents.map(agentCard)}</div>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="mt-14 scroll-mt-28 border-t-2 border-yellow-line/50 pt-8" aria-labelledby="items-heading">
          <div className="flex flex-wrap items-center gap-3">
            <h2 id="items-heading" className="font-display text-2xl text-yellow-ink">
              Items
            </h2>
            <PillButton
              variant="primary"
              className="ml-auto"
              disabled={!rules.data}
              onClick={() => setItemForm({ open: true, item: null })}
            >
              <Plus className="size-4" aria-hidden="true" />
              Add item
            </PillButton>
          </div>
          <TooltipProvider>
            <div className="mt-4 overflow-x-auto rounded-md border-2 border-yellow-line bg-card">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                   <tr className="border-b-2 border-yellow-line bg-yellow-tint">
                    {["Name", "Seller", "Agreed price", "Address", "Status", "Actions"].map((h) => (
                      <th
                        key={h}
                        className={cn(
                          "px-2 py-2 font-semibold",
                          h === "Agreed price" && "text-right",
                        )}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr
                      key={item.tool}
                      className={cn(
                        "border-b border-yellow-line/40",
                        !item.active && "text-ink-muted",
                      )}
                    >
                      <td className="px-2 py-2 font-semibold">{item.name}</td>
                      <td className="px-2 py-2">{item.vendor}</td>
                      <td className="nums px-2 py-2 text-right">{formatUsdc(item.price)}</td>
                      <td className="px-2 py-2">
                        {item.url.startsWith("{vendor_base}") || item.url.startsWith("{news_base}") ? (
                          "Demo seller"
                        ) : (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span
                                tabIndex={0}
                                className="cursor-help underline decoration-dotted"
                              >
                                {item.url.length > 28
                                  ? `${item.url.slice(0, 18)}…${item.url.slice(-8)}`
                                  : truncateAddress(item.url)}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>{item.url}</TooltipContent>
                          </Tooltip>
                        )}
                      </td>
                      <td className="px-2 py-2">{item.active ? "Active" : "Archived"}</td>
                      <td className="px-2 py-2">
                        <div className="flex gap-2">
                          {item.active ? (
                            <>
                              <PillButton
                                className="bg-white px-3 py-1 text-sm sm:text-sm"
                                onClick={() => setItemForm({ open: true, item })}
                              >
                                Edit
                              </PillButton>
                              <PillButton
                                variant="destructive"
                                className="px-3 py-1 text-sm sm:text-sm"
                                onClick={() => setPending({ kind: "item", item, active: false })}
                              >
                                Archive
                              </PillButton>
                            </>
                          ) : (
                            <PillButton
                              className="bg-white px-3 py-1 text-sm sm:text-sm"
                              onClick={() => setPending({ kind: "item", item, active: true })}
                            >
                              Restore
                            </PillButton>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TooltipProvider>
      </section>

      <section className="mt-14 scroll-mt-28 border-t-2 border-slate-400/60 pt-8" aria-labelledby="history-heading">
          <h2 id="history-heading" className="font-display text-2xl text-slate-700">
            Change history
          </h2>
          {history.data && history.data.length === 0 ? (
            <p className="text-ink-muted mt-3">No changes yet.</p>
          ) : null}
          <ul className="mt-4 divide-y divide-slate-300 overflow-hidden rounded-md border-2 border-slate-300 bg-card">
            {[...(history.data ?? [])]
              .sort((a, b) => b.created_at.localeCompare(a.created_at))
              .map((entry) => (
                <HistoryRow key={entry.id} entry={entry} itemName={itemName} />
              ))}
          </ul>
      </section>
        </div>
      </div>

      <AgentForm
        open={agentForm.open}
        onOpenChange={(open) => setAgentForm((current) => ({ ...current, open }))}
        agent={agentForm.agent}
        items={items}
        onSaved={refreshAll}
      />
      <ItemForm
        open={itemForm.open}
        onOpenChange={(open) => setItemForm((current) => ({ ...current, open }))}
        item={itemForm.item}
        onSaved={refreshAll}
      />
      <KeyDialog agentId={keyFor} onClose={() => setKeyFor(null)} />
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(open) => (open ? undefined : setPending(null))}
        title={
          pending
            ? `${pending.active ? "Restore" : "Archive"} ${pending.kind === "agent" ? pending.agent.agent_id : pending.item.name}?`
            : ""
        }
        text={
          pending && !pending.active
            ? pending.kind === "agent"
              ? "The agent can't buy anything until you restore it. Its purchase history is kept."
              : "Agents can't buy this item until you restore it."
            : pending?.kind === "agent"
              ? "The agent can buy again within its rules."
              : "Agents with this item on their list can buy it again."
        }
        confirmLabel={pending?.active ? "Restore" : "Archive"}
        variant={pending?.active ? "primary" : "destructive"}
        onConfirm={applyPending}
      />
    </div>
  );
}

function HistoryRow({
  entry,
  itemName,
}: {
  entry: RulesHistoryEntry;
  itemName: Map<string, string>;
}) {
  const who = entry.actor.toLowerCase() === "operator" ? "Operator" : "Demo visitor";
  const details = Object.entries(entry.details ?? {});
  return (
    <li className="p-4">
      <p className="text-sm">
        <span className="nums text-ink-muted">{formatTime(entry.created_at)}</span>{" "}
        <span className="font-semibold">{who}</span> · {actionLabel[entry.action] ?? entry.action}{" "}
        <span className="font-semibold">{entry.target}</span>
      </p>
      {details.length > 0 ? (
        <ul className="mt-1 space-y-0.5 text-sm">
          {details.map(([field, change]) => {
            const [before, after] = Array.isArray(change) ? change : [undefined, change];
            const map = (v: unknown) =>
              field === "allowed_tools" && Array.isArray(v)
                ? v.map((t) => itemName.get(String(t)) ?? t)
                : v;
            return (
              <li key={field}>
                {fieldLabel[field] ?? field}: {showValue(map(before))} → {showValue(map(after))}
              </li>
            );
          })}
        </ul>
      ) : null}
    </li>
  );
}
