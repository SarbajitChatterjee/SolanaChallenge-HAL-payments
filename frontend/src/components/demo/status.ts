import {
  Ban,
  CheckCircle2,
  CircleSlash,
  Clock,
  Loader2,
  Power,
  Recycle,
  TriangleAlert,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { Tone } from "@/components/ab/Panel";

export type StatusLook = { label: string; tone: Tone; icon: LucideIcon };

const map: Record<string, StatusLook> = {
  settled: { label: "Paid", tone: "paid", icon: CheckCircle2 },
  reused: { label: "Reused, not paid", tone: "paid", icon: Recycle },
  held: { label: "Waiting for you", tone: "waiting", icon: Clock },
  pending: { label: "Waiting for you", tone: "waiting", icon: Clock },
  approved: { label: "Approved", tone: "paid", icon: CheckCircle2 },
  denied: { label: "Denied", tone: "blocked", icon: XCircle },
  blocked: { label: "Blocked", tone: "blocked", icon: Ban },
  failed: { label: "Didn't go through", tone: "blocked", icon: TriangleAlert },
  reserved: { label: "Paying…", tone: "white", icon: Loader2 },
  control: { label: "Kill switch", tone: "ink", icon: Power },
  repeat_purchase: { label: "Repeat blocked", tone: "blocked", icon: Ban },
  circuit_breaker: { label: "Stopped automatically", tone: "blocked", icon: Power },
  seller_under_review: { label: "Seller under review", tone: "waiting", icon: TriangleAlert },
};

export function statusLook(status: string): StatusLook {
  return map[status] ?? { label: status, tone: "white", icon: CircleSlash };
}

export function statusGroup(status: string): "paid" | "waiting" | "blocked" | "other" {
  if (status === "settled" || status === "approved" || status === "reused") return "paid";
  if (status === "held" || status === "pending" || status === "seller_under_review")
    return "waiting";
  if (["blocked", "failed", "denied", "circuit_breaker", "repeat_purchase"].includes(status))
    return "blocked";
  return "other";
}
