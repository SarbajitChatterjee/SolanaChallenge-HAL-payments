import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { KillSwitch } from "@/components/ab/KillSwitch";
import { Panel } from "@/components/ab/Panel";
import type { StateAgent } from "@/lib/api";
import { formatAmount, formatUsdc, toNumber, truncateAddress } from "@/lib/format";
import { cn } from "@/lib/utils";

function Meter({ spent, cap }: { spent: string; cap: string }) {
  const ratio = toNumber(cap) > 0 ? toNumber(spent) / toNumber(cap) : 0;
  const hot = ratio >= 0.99;
  return (
    <div className="mt-1.5 h-2 w-full overflow-hidden rounded-sm bg-white/70">
      <div
        className={cn("h-full transition-all", hot ? "bg-blocked-line" : "bg-sky-line")}
        style={{
          width: `${Math.min(100, Math.max(2, ratio * 100))}%`,
        }}
      />
    </div>
  );
}

function WalletAddress({ address }: { address: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="nums text-xs">{truncateAddress(address)}</span>
      <button
        type="button"
        className="rounded-md p-1 hover:bg-white"
        aria-label={copied ? "Address copied" : "Copy wallet address"}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(address);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1500);
          } catch {
            /* clipboard not available */
          }
        }}
      >
        {copied ? (
          <Check className="size-3.5" aria-hidden="true" />
        ) : (
          <Copy className="size-3.5" aria-hidden="true" />
        )}
      </button>
    </span>
  );
}

export function AgentBand({
  agent,
  itemNames,
  rail,
  busy,
  onToggleFreeze,
  tourTarget,
}: {
  agent: StateAgent;
  itemNames: string[];
  rail: "mock" | "paykit";
  busy: boolean;
  onToggleFreeze: () => void;
  tourTarget: boolean;
}) {
  return (
    <Panel tone="sky" className={cn("relative overflow-hidden", agent.frozen && "hatch")}>
      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr_1fr_auto]">
        <div>
          <h2 className="panel-text font-display text-lg font-bold">{agent.agent_id}</h2>
          <p className="mt-1 text-sm">{agent.description}</p>
          <p className="text-ink-muted mt-2 text-sm">May buy: {itemNames.join(", ")}</p>
        </div>

        <div>
          <p className="text-sm font-semibold">This task</p>
          {agent.current_task ? (
            <>
              <p className="nums text-sm">
                {formatAmount(agent.current_task.spent)} of {formatAmount(agent.per_task_cap)} USDC
              </p>
              <Meter spent={agent.current_task.spent} cap={agent.per_task_cap} />
            </>
          ) : (
            <p className="text-ink-muted text-sm">No task yet</p>
          )}
        </div>

        <div>
          <p className="text-sm font-semibold">Today</p>
          <p className="nums text-sm">
            {formatAmount(agent.spent_today)} of {formatAmount(agent.daily_cap)} USDC
          </p>
          <Meter spent={agent.spent_today} cap={agent.daily_cap} />

          <p className="mt-3 text-sm font-semibold">Wallet</p>
          {rail === "mock" || !agent.wallet_usdc ? (
            <p className="text-ink-muted text-sm">–</p>
          ) : (
            <p className="nums flex flex-wrap items-center gap-2 text-sm">
              {formatUsdc(agent.wallet_usdc)}
              {agent.wallet_address ? <WalletAddress address={agent.wallet_address} /> : null}
            </p>
          )}
          <p className="text-ink-muted nums mt-1 text-xs">
            Needs your OK above {formatAmount(agent.approval_above)} USDC
          </p>
        </div>

        <div className="flex items-start" {...(tourTarget ? { "data-tour": "breaker" } : {})}>
          <KillSwitch
            frozen={agent.frozen}
            busy={busy}
            agentId={agent.agent_id}
            onToggle={onToggleFreeze}
          />
        </div>
      </div>
    </Panel>
  );
}
