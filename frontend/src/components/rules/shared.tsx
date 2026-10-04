import type { ReactNode } from "react";
import { useState } from "react";
import { toast } from "sonner";

import { PillButton, type PillVariant } from "@/components/ab/PillButton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError, NetworkError } from "@/lib/api";

export type FieldErrors = Record<string, string>;

/** 422 errors go under the matching field; everything else becomes a toast. */
export function handleRulesError(error: unknown, setErrors: (errors: FieldErrors) => void) {
  if (error instanceof ApiError && error.status === 422) {
    if (error.field) {
      setErrors({ [error.field]: error.detail });
      return;
    }
    toast.error(error.detail);
    return;
  }
  toastError(error);
}

export function toastError(error: unknown) {
  if (error instanceof ApiError) toast.error(error.detail);
  else if (error instanceof NetworkError) toast.error(error.message);
  else toast.error("Something went wrong. Please try again.");
}

export function Field({
  id,
  label,
  help,
  error,
  children,
}: {
  id: string;
  label: string;
  help?: string;
  error?: string | undefined;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block font-semibold">
        {label}
      </label>
      {help ? <p className="text-ink-muted text-sm">{help}</p> : null}
      {children}
      {error ? (
        <p className="text-blocked-ink text-sm font-semibold" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export const inputClass =
  "w-full rounded-lg border-2 border-[var(--grid)] bg-white px-3 py-2 focus-visible:border-purple-line";

export function UsdcInput({
  id,
  value,
  onChange,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="relative">
      <input
        id={id}
        type="number"
        step="0.01"
        min="0"
        inputMode="decimal"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`${inputClass} nums pr-16`}
      />
      <span className="text-ink-muted pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-sm font-semibold">
        USDC
      </span>
    </div>
  );
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  text,
  confirmLabel,
  variant = "primary",
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  text: string;
  confirmLabel: string;
  variant?: PillVariant;
  onConfirm: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  async function confirm() {
    setBusy(true);
    try {
      await onConfirm();
      onOpenChange(false);
    } catch (error) {
      toastError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">{title}</DialogTitle>
          <DialogDescription>{text}</DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2">
          <PillButton onClick={() => onOpenChange(false)}>Cancel</PillButton>
          <PillButton variant={variant} disabled={busy} onClick={() => void confirm()}>
            {confirmLabel}
          </PillButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
