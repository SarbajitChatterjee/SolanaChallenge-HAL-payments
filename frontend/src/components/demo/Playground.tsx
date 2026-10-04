import {
  Check,
  ChevronDown,
  ExternalLink,
  Loader2,
  Recycle,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Panel, PanelTitle, toneClass } from "@/components/ab/Panel";
import { PillButton } from "@/components/ab/PillButton";
import { statusLook } from "@/components/demo/status";
import { STORAGE_KEYS } from "@/config";
import {
  ApiError,
  NetworkError,
  api,
  type Catalog,
  type ContentFlag,
  type Purchase,
  type State,
} from "@/lib/api";
import { formatAmount } from "@/lib/format";
import { useSettings } from "@/lib/settings";
import { cn } from "@/lib/utils";

const SUSPICIOUS_URL = "https://dossier-deals.example/full-dossier";

// Part of the text HAL's firewall puts in place of removed instructions.
const REMOVED_MARKER = "removed by HAL";

function newTaskId() {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  let suffix = "";
  for (let index = 0; index < 6; index += 1) {
    suffix += chars[Math.floor(Math.random() * chars.length)];
  }
  return `playground-${suffix}`;
}

function flagLabel(flag: ContentFlag, redacted: boolean) {
  if (flag.kind === "agent_instruction")
    return redacted
      ? "Instructions aimed at AI agents (removed)"
      : "Instructions aimed at AI agents (flagged)";
  if (flag.kind === "payment_solicitation") return "A request to pay";
  if (flag.kind === "unlisted_link") return "A link to an unapproved seller";
  return "Not checked";
}

/** A small check in the card's own colours, shown on the selected card. */
function SelectedMark() {
  return (
    <span
      aria-hidden="true"
      className="panel-text absolute top-2.5 right-2.5 grid size-5 place-items-center rounded-full border-[1.5px] border-[var(--pc)] bg-[var(--pt)]"
    >
      <Check className="size-3" strokeWidth={3} />
    </span>
  );
}

type Result = { status: number; purchase: Purchase } | null;

export function Playground({
  catalog,
  state,
  live,
  onChanged,
}: {
  catalog: Catalog;
  state: State;
  live: boolean;
  onChanged: () => void;
}) {
  const { config } = useSettings();
  const [agentId, setAgentId] = useState(catalog.agents[0]?.agent_id ?? "research-agent");
  const firstTool = catalog.items[0]?.tool;
  const [choice, setChoice] = useState<{ tool?: string; url?: string }>(
    firstTool ? { tool: firstTool } : {},
  );
  const [taskId, setTaskId] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result>(null);
  const [error, setError] = useState<string | null>(null);
  const [showJson, setShowJson] = useState(false);
  const choicesRef = useRef<HTMLParagraphElement>(null);

  // Opening "Be the agent" (tab or link) brings the choices into view, below the sticky header.
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    choicesRef.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }, []);

  useEffect(() => {
    const stored = window.sessionStorage.getItem(STORAGE_KEYS.playgroundTask);
    if (stored) {
      setTaskId(stored);
    } else {
      const next = newTaskId();
      window.sessionStorage.setItem(STORAGE_KEYS.playgroundTask, next);
      setTaskId(next);
    }
  }, []);

  function startNewTask() {
    const next = newTaskId();
    window.sessionStorage.setItem(STORAGE_KEYS.playgroundTask, next);
    setTaskId(next);
    setResult(null);
    setError(null);
  }

  const agent = catalog.agents.find((entry) => entry.agent_id === agentId) ?? catalog.agents[0];
  const stateAgent = state.agents.find((entry) => entry.agent_id === agentId);
  const taskSpent =
    stateAgent?.current_task?.task_id === taskId ? stateAgent.current_task.spent : "0.00";

  const body = useMemo(
    () => ({ agent_id: agentId, task_id: taskId, ...choice }),
    [agentId, taskId, choice],
  );

  async function buy(extra?: { approval_id: string }) {
    if (!live) {
      setError("Connect the API in Settings to try a real purchase.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const answer = await api.playgroundBuy(config, { ...body, ...extra });
      setResult(answer);
      onChanged();
    } catch (caught) {
      if (caught instanceof NetworkError) {
        setError(
          `Can't reach the API at ${caught.baseUrl}. Free servers take about 30 seconds to wake up.`,
        );
      } else if (caught instanceof ApiError) {
        setError(caught.detail);
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function decide(approve: boolean) {
    if (!result?.purchase.approval_id) return;
    const approvalId = result.purchase.approval_id;
    setBusy(true);
    setError(null);
    try {
      if (approve) {
        await api.approve(config, approvalId);
        const answer = await api.playgroundBuy(config, { ...body, approval_id: approvalId });
        setResult(answer);
      } else {
        await api.deny(config, approvalId);
        const answer = await api.playgroundBuy(config, { ...body, approval_id: approvalId });
        setResult(answer);
      }
      onChanged();
    } catch (caught) {
      if (caught instanceof ApiError) setError(caught.detail);
      else setError("Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const look = result ? statusLook(result.purchase.status) : null;
  const flags = (result?.purchase.content_flags ?? []).filter(
    (flag) => flag.kind !== "not_scanned",
  );
  const redacted = JSON.stringify(result?.purchase.data ?? "").includes(REMOVED_MARKER);

  return (
    <div className="space-y-6">
      <p ref={choicesRef} className="text-ink-muted scroll-mt-24">
        You&apos;re the agent now. Pick what to buy and see what HAL does.
      </p>

      <Panel tone="sky">
        <PanelTitle>Which agent are you?</PanelTitle>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {catalog.agents.map((option) => (
            <button
              key={option.agent_id}
              type="button"
              onClick={() => setAgentId(option.agent_id)}
              aria-pressed={agentId === option.agent_id}
              className={cn(
                "panel-flat relative p-4 pr-10 text-left",
                agentId === option.agent_id ? "panel-yellow" : "panel-white",
              )}
            >
              {agentId === option.agent_id ? <SelectedMark /> : null}
              <span className="font-display block font-bold">{option.agent_id}</span>
              <span className="mt-1 block text-sm">{option.description}</span>
              <span className="text-ink-muted nums mt-2 block text-xs">
                Task budget {formatAmount(option.per_task_cap)} USDC · daily{" "}
                {formatAmount(option.daily_cap)} USDC · your OK above{" "}
                {formatAmount(option.approval_above)} USDC
              </span>
            </button>
          ))}
        </div>
      </Panel>

      <Panel tone="pink">
        <PanelTitle>What do you want to buy?</PanelTitle>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {catalog.items.map((item) => (
            <button
              key={item.tool}
              type="button"
              onClick={() => setChoice({ tool: item.tool })}
              aria-pressed={choice.tool === item.tool}
              className={cn(
                "panel-flat relative p-4 pr-10 text-left",
                choice.tool === item.tool ? "panel-yellow" : "panel-white",
              )}
            >
              {choice.tool === item.tool ? <SelectedMark /> : null}
              <span className="font-display block font-bold">{item.name}</span>
              <span className="mt-1 block text-sm">{item.description}</span>
              <span className="text-ink-muted mt-2 block text-xs">{item.vendor}</span>
              <span className="nums mt-1 block font-bold">{formatAmount(item.price)} USDC</span>
            </button>
          ))}
          <button
            type="button"
            onClick={() => setChoice({ url: SUSPICIOUS_URL })}
            aria-pressed={choice.url === SUSPICIOUS_URL}
            className={cn(
              "panel-flat relative p-4 pr-10 text-left",
              choice.url === SUSPICIOUS_URL ? "panel-waiting" : "panel-blocked",
            )}
          >
            {choice.url === SUSPICIOUS_URL ? <SelectedMark /> : null}
            <TriangleAlert className="panel-text size-5" aria-hidden="true" />
            <span className="font-display mt-1 block font-bold">A link from a news result</span>
            <span className="mt-1 block text-sm">
              A 25 USDC &quot;full dossier&quot; from a seller you&apos;ve never seen.
            </span>
          </button>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <PillButton variant="primary" onClick={() => buy()} disabled={busy || !taskId}>
            {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
            Ask to buy
          </PillButton>
          <span className="nums text-sm font-semibold">
            Your task budget: {formatAmount(taskSpent)} of{" "}
            {formatAmount(agent?.per_task_cap ?? "0")} USDC
          </span>
          <PillButton onClick={startNewTask}>Start a new task</PillButton>
        </div>

        {error ? (
          <p
            className="panel-flat panel-blocked panel-text mt-4 p-3 text-sm font-semibold"
            role="status"
            aria-live="polite"
          >
            {error}
          </p>
        ) : null}
      </Panel>

      {result && look ? (
        <div className="slide-in space-y-3">
          {flags.length > 0 ? (
            <div className="panel-flat panel-waiting p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="panel-text flex items-center gap-2 font-display font-bold">
                  <ShieldCheck className="size-5" aria-hidden="true" />
                  HAL checked what the seller sent back
                </p>
                <span
                  className={cn(
                    "panel-flat panel-text inline-flex items-center px-2.5 py-1 text-xs font-bold",
                    toneClass[redacted ? "paid" : "waiting"],
                  )}
                >
                  {redacted ? "Removed" : "Flagged"}
                </span>
              </div>
              <ul className="mt-3 space-y-3">
                {flags.map((flag, index) => (
                  <li key={`${flag.path}-${index}`}>
                    <p className="text-sm font-semibold">{flagLabel(flag, redacted)}</p>
                    <code className="text-ink mt-1.5 block rounded border border-border/60 bg-muted/50 p-2 font-mono text-xs break-all">
                      {flag.extract}
                    </code>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className={cn("panel p-5", toneClass[look.tone])}>
            <p className="panel-text flex items-center gap-2 font-display text-lg font-bold">
              <look.icon className="size-5" aria-hidden="true" />
              {look.label}
            </p>
            <p className="mt-2">{result.purchase.reason}</p>
            {result.purchase.caused_by_seller ? (
              <p className="text-ink-muted mt-1 text-sm">
                This link came from {result.purchase.caused_by_seller}.
              </p>
            ) : null}
            {result.purchase.status === "reused" ? (
              <p className="nums mt-2 flex items-center gap-1.5 text-sm font-semibold">
                <Recycle className="size-4" aria-hidden="true" />
                0.00 USDC · reused an earlier result · saved{" "}
                {formatAmount(result.purchase.saved ?? "0")} USDC
              </p>
            ) : null}
            {result.purchase.item_name || result.purchase.amount ? (
              <p className="nums mt-2 text-sm font-semibold">
                {result.purchase.item_name ?? ""}
                {result.purchase.amount ? ` · ${formatAmount(result.purchase.amount)} USDC` : ""}
              </p>
            ) : null}

            {result.purchase.explorer_url ? (
              <a
                className="mt-3 inline-flex items-center gap-1 font-semibold underline"
                href={result.purchase.explorer_url}
                target="_blank"
                rel="noreferrer"
              >
                View receipt
                <ExternalLink className="size-3.5" aria-hidden="true" />
              </a>
            ) : result.purchase.tx?.startsWith("mock-") ? (
              <p className="text-ink-muted mt-3 text-sm">Test receipt {result.purchase.tx}</p>
            ) : null}

            {result.status === 202 && result.purchase.approval_id ? (
              <div className="mt-4 flex gap-2">
                <PillButton variant="paid" disabled={busy} onClick={() => decide(true)}>
                  Approve
                </PillButton>
                <PillButton variant="destructive" disabled={busy} onClick={() => decide(false)}>
                  Deny
                </PillButton>
              </div>
            ) : null}
          </div>

          <div className="panel-flat panel-white p-4">
            <button
              type="button"
              className="flex w-full items-center justify-between font-semibold"
              onClick={() => setShowJson((value) => !value)}
              aria-expanded={showJson}
            >
              What your agent&apos;s code receives
              <ChevronDown
                className={cn("size-4 transition-transform", showJson && "rotate-180")}
                aria-hidden="true"
              />
            </button>
            {showJson ? (
              <pre className="mt-3 overflow-x-auto text-xs leading-relaxed">
                <code>{JSON.stringify(result.purchase, null, 2)}</code>
              </pre>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
