import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";
import { toneClass, type Tone } from "./Panel";

export type PillVariant = "primary" | "neutral" | "destructive" | "purple" | "paid";

const variantTone: Record<PillVariant, Tone> = {
  primary: "yellow",
  neutral: "white",
  destructive: "blocked",
  purple: "purple",
  paid: "paid",
};

const base = "pill pill-lift disabled:opacity-55 disabled:cursor-not-allowed text-sm sm:text-base";

/** Shared pill styling, for buttons, router links and plain anchors. */
export function pillClass(variant: PillVariant = "neutral", className?: string) {
  return cn(base, toneClass[variantTone[variant]], className);
}

export function PillButton({
  variant = "neutral",
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: PillVariant }) {
  return <button className={pillClass(variant, className)} {...rest} />;
}

export function PillAnchor({
  variant = "neutral",
  className,
  ...rest
}: React.AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: PillVariant }) {
  return <a className={pillClass(variant, className)} {...rest} />;
}
