import { useMemo, useState } from "react";

import { Panel } from "@/components/ab/Panel";
import { Slider } from "@/components/ui/slider";
import { formatUsd } from "@/lib/format";

const MIN_N = 100;
const MAX_N = 100_000;
const SOLANA_FEE = 0.0013;

function sliderToCount(value: number) {
  const min = Math.log10(MIN_N);
  const max = Math.log10(MAX_N);
  const raw = 10 ** (min + (value / 100) * (max - min));
  if (raw >= 10_000) return Math.round(raw / 1000) * 1000;
  if (raw >= 1000) return Math.round(raw / 100) * 100;
  return Math.round(raw / 10) * 10;
}

function countToSlider(count: number) {
  const min = Math.log10(MIN_N);
  const max = Math.log10(MAX_N);
  return ((Math.log10(count) - min) / (max - min)) * 100;
}

function Bar({
  label,
  value,
  max,
  tone,
}: {
  label: string;
  value: number;
  max: number;
  tone: "blocked" | "paid";
}) {
  const width = max > 0 ? Math.max(2, (value / max) * 100) : 2;
  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-sm font-semibold">{label}</span>
        <span className="nums font-display text-lg font-bold">{formatUsd(value)} USD</span>
      </div>
      <div className="mt-1.5 h-4 w-full overflow-hidden rounded-sm border-2 border-[var(--grid)] bg-white p-[2px]">
        <div
          className={`h-full rounded-[2px] transition-all ${tone === "blocked" ? "bg-blocked-line" : "bg-paid-line"}`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

export function CostCalculator() {
  const [countSlider, setCountSlider] = useState(() => countToSlider(1000));
  const [cents, setCents] = useState(2);

  const count = useMemo(() => sliderToCount(countSlider), [countSlider]);
  const price = cents / 100;

  const cardFees = count * (0.3 + 0.029 * price);
  const solanaFees = count * SOLANA_FEE;
  const value = count * price;
  const multiple = value > 0 ? cardFees / value : 0;

  return (
    <Panel tone="purple">
      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-5">
          <div>
            <label htmlFor="purchases" className="text-sm font-semibold">
              Purchases per month
            </label>
            <div className="nums font-display mt-0.5 text-2xl font-bold">
              {count.toLocaleString("en-US")}
            </div>
            <Slider
              id="purchases"
              className="mt-3"
              value={[countSlider]}
              min={0}
              max={100}
              step={0.5}
              onValueChange={([next]) => setCountSlider(next ?? 0)}
              aria-label="Purchases per month"
            />
          </div>
          <div>
            <label htmlFor="price" className="text-sm font-semibold">
              Average price
            </label>
            <div className="nums font-display mt-0.5 text-2xl font-bold">{cents} cents</div>
            <Slider
              id="price"
              className="mt-3"
              value={[cents]}
              min={1}
              max={50}
              step={1}
              onValueChange={([next]) => setCents(next ?? 1)}
              aria-label="Average price in cents"
            />
          </div>
        </div>

        <div className="space-y-4">
          <Bar
            label="Typical online card fees (2.9% + 0.30 USD each)"
            value={cardFees}
            max={Math.max(cardFees, solanaFees, value)}
            tone="blocked"
          />
          <Bar
            label="Solana network fees (about 0.0013 USD each)"
            value={solanaFees}
            max={Math.max(cardFees, solanaFees, value)}
            tone="paid"
          />
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-t-2 border-[var(--pc)] pt-3">
            <span className="text-sm font-semibold">Value of what the agent bought</span>
            <span className="nums font-display text-lg font-bold">{formatUsd(value)} USD</span>
          </div>
          <p className="panel-flat panel-white p-3 font-semibold" aria-live="polite">
            Card fees would be {multiple >= 10 ? Math.round(multiple) : multiple.toFixed(1)}× the
            value of the data. On Solana they&apos;re {formatUsd(solanaFees)} USD.
          </p>
        </div>
      </div>
      <p className="text-ink-muted mt-5 text-xs">
        Card example uses typical online card pricing. Solana figure is the median network fee
        reported by Solana Pay Kit. Your numbers will vary.
      </p>
    </Panel>
  );
}
