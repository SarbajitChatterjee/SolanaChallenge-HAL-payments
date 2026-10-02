import { cn } from "@/lib/utils";

/**
 * The signature control: a 44x64 housing with a lever that sits up when the
 * agent is running and down when it is stopped.
 */
export function KillSwitch({
  frozen,
  busy,
  onToggle,
  agentId,
  ...rest
}: {
  frozen: boolean;
  busy?: boolean;
  onToggle: () => void;
  agentId: string;
} & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("flex items-center gap-3")} {...rest}>
      <button
        type="button"
        role="switch"
        aria-checked={!frozen}
        aria-label={frozen ? `Let ${agentId} buy again` : `Stop ${agentId} from spending`}
        disabled={busy}
        onClick={onToggle}
        className="panel-yellow panel-flat relative h-16 w-11 shrink-0 p-0 disabled:opacity-60"
      >
        <span
          className={cn(
            "absolute left-1/2 h-6 w-6 -translate-x-1/2 rounded-md border-[3px] transition-all duration-150",
            frozen ? "top-8" : "top-1.5",
          )}
          style={{ backgroundColor: "#A16207", borderColor: "#7A4A05" }}
          aria-hidden="true"
        />
      </button>
      <div className="leading-tight">
        <div className="panel-text font-bold" style={{ color: frozen ? "#B91C1C" : "#A16207" }}>
          {frozen ? "Stopped" : "Running"}
        </div>
        <div className="text-ink-muted text-xs">
          {frozen ? "Flip to let it buy again" : "Flip to stop spending"}
        </div>
      </div>
    </div>
  );
}
