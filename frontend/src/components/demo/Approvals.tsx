import { Panel, PanelTitle } from "@/components/ab/Panel";
import { PillButton } from "@/components/ab/PillButton";
import type { StateApproval } from "@/lib/api";
import { formatAmount } from "@/lib/format";

export function Approvals({
  approvals,
  busyId,
  onApprove,
  onDeny,
}: {
  approvals: StateApproval[];
  busyId: string | null;
  onApprove: (id: string) => void;
  onDeny: (id: string) => void;
}) {
  if (approvals.length === 0) return null;

  return (
    <Panel tone="pink" data-tour="approvals">
      <PanelTitle>Waiting for you</PanelTitle>
      <ul className="mt-4 space-y-3" aria-live="assertive">
        {approvals.map((approval) => (
          <li
            key={approval.id}
            className="panel-flat panel-white flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div>
              <p>
                <strong>{approval.agent_id}</strong> wants{" "}
                <strong>{approval.item_name ?? approval.tool ?? "something"}</strong>
                {approval.vendor ? ` from ${approval.vendor}` : ""} for{" "}
                <strong className="nums">{formatAmount(approval.amount)} USDC</strong>
              </p>
              <p className="text-ink-muted mt-1 text-sm">{approval.reason}</p>
            </div>
            <div className="flex shrink-0 gap-2">
              <PillButton
                variant="paid"
                disabled={busyId === approval.id}
                onClick={() => onApprove(approval.id)}
              >
                Approve
              </PillButton>
              <PillButton
                variant="destructive"
                disabled={busyId === approval.id}
                onClick={() => onDeny(approval.id)}
              >
                Deny
              </PillButton>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
