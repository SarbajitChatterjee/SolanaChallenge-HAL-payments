import { Ban, CircleSlash, Clock, Loader2, Power, TriangleAlert, CheckCircle2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { Tone } from "@/components/ab/Panel";

export type StatusLook = { label: string; tone: Tone; icon: LucideIcon };

const map: Record<string, StatusLook> = {
  settled: { label: "Paid", tone: "paid", icon: CheckCircle2 },
  held: { label: "Waiting for you", tone: "waiting", icon: Clock },
  pending: { label: "Waiting for you", tone: "waiting", icon: Clock },
  blocked: { label: "Blocked", tone: "blocked", icon: Ban },
  failed: { label: "Didn't go through", tone: "blocked", icon: TriangleAlert },
  reserved: { label: "Paying…", tone: "white", icon: Loader2 },
  control: { label: "Kill switch", tone: "ink", icon: Power },
};

export function statusLook(status: string): StatusLook {
  return map[status] ?? { label: status, tone: "white", icon: CircleSlash };
}

export function statusGroup(status: string): "paid" | "waiting" | "blocked" | "other" {
  if (status === "settled") return "paid";
  if (status === "held" || status === "pending") return "waiting";
  if (status === "blocked" || status === "failed") return "blocked";
  return "other";
}
