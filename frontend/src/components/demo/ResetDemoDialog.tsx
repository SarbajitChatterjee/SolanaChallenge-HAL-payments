import { RotateCcw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { PillButton } from "@/components/ab/PillButton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError, NetworkError } from "@/lib/api";

export function ResetDemoDialog({
  open,
  onOpenChange,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);

  async function confirm() {
    setBusy(true);
    try {
      await onConfirm();
      onOpenChange(false);
    } catch (error) {
      if (error instanceof ApiError) toast.error(error.detail);
      else if (error instanceof NetworkError) toast.error(error.message);
      else toast.error("Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">Reset the demo?</DialogTitle>
          <DialogDescription>
            This demo runs on dummy data, dummy sellers and test wallets. Nothing here is a real
            purchase. Resetting clears all purchases and approvals, restores the starting rules,
            switches every agent back on and refills the test wallets. Sign-ups and the change
            history are kept. Reset Button is also present only for demonstrative purposes.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2">
          <PillButton onClick={() => onOpenChange(false)}>Cancel</PillButton>
          <PillButton variant="destructive" disabled={busy} onClick={() => void confirm()}>
            <RotateCcw className="size-4" aria-hidden="true" />
            Reset demo
          </PillButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
