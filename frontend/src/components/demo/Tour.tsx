import { Link } from "@tanstack/react-router";
import { Check, Loader2, X, RotateCcw } from "lucide-react";
import { useEffect, useRef } from "react";

import { Panel } from "@/components/ab/Panel";
import { PillButton, pillClass } from "@/components/ab/PillButton";
import type { Demo, TourStep } from "@/lib/api";
import { cn } from "@/lib/utils";

export function TourIntro({
  onStart,
  onClose,
  busy,
}: {
  onStart: () => void;
  onClose: () => void;
  busy: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ref.current?.querySelector<HTMLButtonElement>("button")?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-[rgba(42,39,71,0.45)] p-4">
      <Panel
        tone="yellow"
        className="w-full max-w-lg"
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-intro-title"
      >
        <div ref={ref}>
          <h2 id="tour-intro-title" className="panel-text font-display text-2xl">
            You&apos;re in charge for 3 minutes.
          </h2>
          <p className="mt-3">
            An AI agent is about to check a new supplier and buy the data it needs. You&apos;ll
            watch each purchase and see what HAL does. Twice, you&apos;ll have to act.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <PillButton variant="primary" className="bg-white" onClick={onStart} disabled={busy}>
              {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
              Start
            </PillButton>
            <PillButton onClick={onClose}>Not now</PillButton>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function Dots({ index, total }: { index: number; total: number }) {
  return (
    <div className="mt-2 flex gap-1.5" aria-hidden="true">
      {Array.from({ length: total }).map((_, position) => (
        <span
          key={position}
          className={cn("h-2 flex-1 rounded-full", position < index ? "bg-[#4ADE80]" : "bg-white")}
        />
      ))}
    </div>
  );
}

export function TourCard({
  demo,
  steps,
  busy,
  onNext,
  onStop,
  onTryYourself,
  onDownload,
  onReset,
}: {
  demo: Demo;
  steps: TourStep[];
  busy: boolean;
  onNext: () => void;
  onStop: () => void;
  onTryYourself: () => void;
  onDownload: () => void;
  onReset?: (() => void) | undefined;
}) {
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    cardRef.current?.focus();
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onStop();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onStop]);

  const stepIndex = demo.step_index;
  const total = demo.step_total || steps.length;
  const current = steps.find((step) => step.index === stepIndex) ?? steps[stepIndex - 1];
  const previous = steps.find((step) => step.index === stepIndex - 1);

  // Between steps, count the step that just finished; while a step runs or waits for you, count that step.
  const stepLabel =
    demo.waiting_for === "next" && stepIndex > 1
      ? `Step ${stepIndex - 1} of ${total} done`
      : `Step ${Math.min(stepIndex, total)} of ${total}`;

  return (
    <div
      className={cn(
        "fixed z-50",
        "inset-x-0 bottom-0 sm:inset-x-auto sm:right-6 sm:bottom-6 sm:w-[25rem]",
      )}
    >
      <Panel
        tone="yellow"
        className="max-h-[70vh] overflow-y-auto rounded-b-none sm:rounded-b-md"
        role="dialog"
        aria-modal="false"
        aria-label="Guided tour"
      >
        <div ref={cardRef} tabIndex={-1} className="outline-none">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              {demo.finished ? (
                <p className="text-sm font-bold">Done</p>
              ) : (
                <p className="nums text-sm font-bold">{stepLabel}</p>
              )}
              <Dots index={demo.finished ? total : stepIndex - 1} total={total} />
            </div>
            <button
              type="button"
              onClick={onStop}
              aria-label="End tour"
              className="panel-flat panel-white grid size-8 place-items-center"
            >
              <X className="size-4" aria-hidden="true" />
            </button>
          </div>

          <div className="mt-4 space-y-4">
            {demo.error ? (
              <>
                <p className="panel-flat panel-blocked panel-text p-3 font-semibold">
                  {demo.error}
                </p>
                {onReset ? (
                  <PillButton variant="destructive" onClick={onReset}>
                    <RotateCcw className="size-4" aria-hidden="true" />
                    Reset demo
                  </PillButton>
                ) : (
                  <PillButton variant="primary" className="bg-white" onClick={onNext}>
                    Start again
                  </PillButton>
                )}
              </>
            ) : demo.finished ? (
              <>
                <h3 className="panel-text font-display text-xl">That&apos;s HAL.</h3>
                <ul className="space-y-2">
                  {steps.map((step) => (
                    <li key={step.key} className="flex items-start gap-2 text-sm">
                      <Check className="mt-0.5 size-4 shrink-0" style={{ color: "#15803D" }} />
                      <span>{step.title}</span>
                    </li>
                  ))}
                </ul>
                <div className="flex flex-wrap gap-2">
                  <PillButton variant="primary" className="bg-white" onClick={onTryYourself}>
                    Try it yourself
                  </PillButton>
                  <Link to="/early-access" className={pillClass()}>
                    Get early access
                  </Link>
                  <PillButton onClick={onDownload}>Download the ledger</PillButton>
                </div>
              </>
            ) : demo.waiting_for === "approval" ? (
              <>
                <p className="panel-flat panel-waiting panel-text p-3 font-bold">Your turn</p>
                <p>{current?.your_turn ?? "Approve or deny the purchase in Waiting for you."}</p>
                <p className="text-ink-muted flex items-center gap-2 text-sm">
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  The tour goes on once you decide.
                </p>
              </>
            ) : demo.waiting_for === "kill_switch_on" ? (
              <>
                <p className="panel-flat panel-waiting panel-text p-3 font-bold">
                  Your turn: flip the yellow switch next to research-agent.
                </p>
                {current?.your_turn ? <p>{current.your_turn}</p> : null}
              </>
            ) : demo.waiting_for === "kill_switch_off" ? (
              <>
                <p className="panel-flat panel-waiting panel-text p-3 font-bold">
                  It was refused. Now flip the switch back.
                </p>
                {current?.your_turn ? <p>{current.your_turn}</p> : null}
              </>
            ) : demo.waiting_for === "next" ? (
              <>
                {previous ? (
                  <div className="panel-flat panel-paid panel-text p-3">
                    <p className="flex items-start gap-2 font-bold">
                      <Check className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                      Done: {previous.title}
                    </p>
                    <p className="mt-1 text-sm">{previous.why_it_matters}</p>
                  </div>
                ) : null}
                <div>
                  <p className="font-bold">Up next: {current?.title}</p>
                  <p className="mt-1">{current?.what_happens}</p>
                  {current?.your_turn && current.key === "ledger" ? (
                    <p className="mt-2 text-sm">{current.your_turn}</p>
                  ) : null}
                </div>
                <PillButton variant="primary" className="bg-white" onClick={onNext} disabled={busy}>
                  {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
                  {current?.key === "ledger" ? "Finish the tour" : `Run step ${stepIndex}`}
                </PillButton>
              </>
            ) : (
              <>
                <p className="font-bold">{current?.title}</p>
                <p>{current?.what_happens}</p>
                <p className="text-ink-muted flex items-center gap-2 text-sm">
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  Watching the agent…
                </p>
              </>
            )}
          </div>
        </div>
      </Panel>
    </div>
  );
}
