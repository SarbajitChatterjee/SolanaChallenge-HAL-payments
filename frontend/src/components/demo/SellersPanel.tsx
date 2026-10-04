import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Panel, PanelTitle } from "@/components/ab/Panel";
import { PillButton } from "@/components/ab/PillButton";
import { ApiError, api } from "@/lib/api";
import { useSellers } from "@/lib/queries";
import { useSettings } from "@/lib/settings";
import { cn } from "@/lib/utils";

export function SellersPanel({ pollMs = false }: { pollMs?: number | false }) {
  const { config } = useSettings();
  const client = useQueryClient();
  const sellers = useSellers(pollMs);
  const [busy, setBusy] = useState<string | null>(null);

  if (!sellers.data || sellers.data.length === 0) return null;

  async function endReview(origin: string) {
    setBusy(origin);
    try {
      await api.restoreSeller(config, origin);
      toast.success("Review ended. Purchases from this seller are automatic again.");
      void client.invalidateQueries({ queryKey: ["sellers"] });
      void client.invalidateQueries({ queryKey: ["state"] });
    } catch (caught) {
      toast.error(caught instanceof ApiError ? caught.detail : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Panel tone="white">
      <PanelTitle>Sellers</PanelTitle>
      <ul className="mt-4 space-y-3">
        {sellers.data.map((seller) => {
          const review = seller.status === "under_review";
          return (
            <li
              key={seller.seller_origin}
              className={cn(
                "panel-flat flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between",
                review ? "panel-waiting" : "panel-white",
              )}
            >
              <div className="min-w-0">
                <p className="font-semibold">{seller.vendors.join(", ") || seller.seller_origin}</p>
                <p className="text-ink-muted truncate text-xs">{seller.seller_origin}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span
                  className={cn(
                    "panel-flat panel-text px-2 py-0.5 text-xs font-bold",
                    review ? "panel-waiting" : "panel-paid",
                  )}
                >
                  {review ? "Under review" : "Active"}
                </span>
                <span className="nums text-ink-muted text-xs">
                  {seller.incidents} {seller.incidents === 1 ? "incident" : "incidents"}
                </span>
                {review ? (
                  <PillButton
                    disabled={busy === seller.seller_origin}
                    onClick={() => void endReview(seller.seller_origin)}
                  >
                    End review
                  </PillButton>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
