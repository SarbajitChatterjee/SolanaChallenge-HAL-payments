/** Format a decimal string with exactly 2 decimals, without float math. */
export function formatAmount(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "–";
  const negative = value.trim().startsWith("-");
  const raw = negative ? value.trim().slice(1) : value.trim();
  const [whole = "0", fraction = ""] = raw.split(".");
  const padded = (fraction + "00").slice(0, 2);
  const digits = whole.replace(/^0+(?=\d)/, "");
  return `${negative ? "-" : ""}${digits || "0"}.${padded}`;
}

export function formatUsdc(value: string | null | undefined): string {
  const amount = formatAmount(value);
  return amount === "–" ? "–" : `${amount} USDC`;
}

/** Decimal string -> number. Only for meters and comparisons, never for display. */
export function toNumber(value: string | null | undefined): number {
  if (!value) return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function truncateAddress(address: string): string {
  if (address.length <= 12) return address;
  return `${address.slice(0, 5)}…${address.slice(-4)}`;
}

export function formatUsd(value: number): string {
  if (value >= 1000) {
    return value.toLocaleString("en-US", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  }
  return value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
