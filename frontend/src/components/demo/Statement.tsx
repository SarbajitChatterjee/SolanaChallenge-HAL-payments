import { ArrowRight, Clock, ExternalLink } from "lucide-react";
import { useMemo, useState } from "react";

import { Panel, toneClass } from "@/components/ab/Panel";
import { statusGroup, statusLook } from "@/components/demo/status";
import type { LedgerEvent } from "@/lib/api";
import { formatAmount, formatTime } from "@/lib/format";
import { cn } from "@/lib/utils";

type Filter = "all" | "paid" | "waiting" | "blocked";

const filters: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "paid", label: "Paid" },
  { value: "waiting", label: "Waiting" },
  { value: "blocked", label: "Blocked" },
];

export function Statement({
  events,
  agentIds,
  newIds,
  changedStatuses = new Map<string, string>(),
}: {
  events: LedgerEvent[];
  agentIds: string[];
  newIds: Set<string>;
  changedStatuses?: Map<string, string>;
}) {
  const [agent, setAgent] = useState("all");
  const [filter, setFilter] = useState<Filter>("all");

  const rows = useMemo(() => {
    return events
      .filter((event) => (agent === "all" ? true : event.agent_id === agent))
      .filter((event) => (filter === "all" ? true : statusGroup(event.status) === filter))
      .slice()
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [events, agent, filter]);

  return (
    <Panel tone="mint" data-tour="statement">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="agent-filter" className="text-sm font-semibold">
          Agent
        </label>
        <select
          id="agent-filter"
          value={agent}
          onChange={(event) => setAgent(event.target.value)}
          className="panel-flat panel-white px-3 py-1.5 text-sm font-semibold"
        >
          <option value="all">All agents</option>
          {agentIds.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
        <div className="ml-auto flex flex-wrap gap-1.5">
          {filters.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setFilter(option.value)}
              aria-pressed={filter === option.value}
              className={cn(
                "panel-flat px-3 py-1.5 text-sm font-semibold",
                filter === option.value ? "panel-yellow panel-text" : "panel-white",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="text-ink-muted mt-6 text-sm">
          Nothing yet. Start the guided tour, or try a purchase in Be the agent.
        </p>
      ) : (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[46rem] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b-[3px] border-[var(--pc)]">
                <th className="py-2 pr-3 font-bold">Time</th>
                <th className="py-2 pr-3 font-bold">Agent</th>
                <th className="py-2 pr-3 font-bold">Purchase</th>
                <th className="py-2 pr-3 text-right font-bold">Amount</th>
                <th className="py-2 pr-3 font-bold">What happened</th>
                <th className="py-2 font-bold">Receipt</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((event) => {
                const look = statusLook(event.status);
                const blocked = event.status === "blocked" || event.status === "failed";
                const isDecision = event.status === "approved" || event.status === "denied";
                const changedStatus = changedStatuses.get(event.id);
                return (
                  <tr
                    key={event.id}
                    className={cn(
                      "border-b border-[var(--pc)] align-top last:border-0",
                      newIds.has(event.id) && "row-new",
                      changedStatus === "approved" && "row-status-approved",
                      changedStatus === "denied" && "row-status-denied",
                    )}
                    style={blocked ? { borderLeft: "4px solid #F87171" } : undefined}
                  >
                    <td className="nums py-3 pr-3 whitespace-nowrap">
                      {formatTime(event.created_at)}
                    </td>
                    <td className="py-3 pr-3 whitespace-nowrap">{event.agent_id}</td>
                    <td className="py-3 pr-3">
                      <span className="font-semibold">
                        {event.item_name ?? event.url ?? event.tool ?? "–"}
                      </span>
                      {event.vendor ? (
                        <span className="text-ink-muted block text-xs">{event.vendor}</span>
                      ) : null}
                    </td>
                    <td className="nums py-3 pr-3 text-right whitespace-nowrap">
                      {event.amount ? `${formatAmount(event.amount)} USDC` : "–"}
                    </td>
                    <td className="py-3 pr-3">
                      <div className="flex flex-wrap items-center gap-1.5">
                        {isDecision ? (
                          <>
                            <span className="panel-flat panel-waiting panel-text inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold">
                              <Clock className="size-3.5" aria-hidden="true" />
                              Waiting for you
                            </span>
                            <ArrowRight
                              className="text-ink-muted size-3.5 shrink-0"
                              aria-hidden="true"
                            />
                          </>
                        ) : null}
                        <span
                          className={cn(
                            "panel-flat panel-text inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold",
                            toneClass[look.tone],
                          )}
                        >
                          <look.icon className="size-3.5" aria-hidden="true" />
                          {look.label}
                        </span>
                      </div>
                      <span className="text-ink-muted mt-1 block text-xs">{event.reason}</span>
                    </td>
                    <td className="py-3 whitespace-nowrap">
                      {event.explorer_url ? (
                        <a
                          className="inline-flex items-center gap-1 font-semibold underline"
                          href={event.explorer_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          View receipt
                          <ExternalLink className="size-3.5" aria-hidden="true" />
                        </a>
                      ) : event.tx?.startsWith("mock-") ? (
                        <span className="text-ink-muted">Test receipt</span>
                      ) : (
                        <span className="text-ink-muted">–</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
