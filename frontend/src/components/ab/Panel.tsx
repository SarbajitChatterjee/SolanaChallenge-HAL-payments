import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export type Tone =
  "sky" | "pink" | "yellow" | "mint" | "purple" | "paid" | "blocked" | "waiting" | "white" | "ink" | "slate";

export const toneClass: Record<Tone, string> = {
  sky: "panel-sky",
  pink: "panel-pink",
  yellow: "panel-yellow",
  mint: "panel-mint",
  purple: "panel-purple",
  paid: "panel-paid",
  blocked: "panel-blocked",
  waiting: "panel-waiting",
  white: "panel-white",
  ink: "panel-ink",
  slate: "panel-slate",
};

export const toneBorderColor: Record<Tone, string> = {
  sky: "#38BDF8",
  pink: "#F472B6",
  yellow: "#FACC15",
  mint: "#34D399",
  purple: "#A78BFA",
  paid: "#4ADE80",
  blocked: "#F87171",
  waiting: "#FBBF24",
  white: "#E4E0F7",
  ink: "#2A2747",
  slate: "#94A3B8",
};

type PanelProps = HTMLAttributes<HTMLDivElement> & { tone?: Tone; flat?: boolean };

export function Panel({ tone = "white", flat = false, className, ...rest }: PanelProps) {
  return (
    <div
      className={cn(flat ? "panel-flat" : "panel", toneClass[tone], "p-5 sm:p-6", className)}
      {...rest}
    />
  );
}

export function PanelTitle({
  as: Heading = "h3",
  className,
  ...rest
}: HTMLAttributes<HTMLHeadingElement> & { as?: "h1" | "h2" | "h3" | "h4" }) {
  return <Heading className={cn("panel-text text-lg font-bold", className)} {...rest} />;
}
