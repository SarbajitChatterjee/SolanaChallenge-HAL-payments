import { useQuery } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";

import { CopyButton } from "@/components/ab/CopyButton";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ApiError, api } from "@/lib/api";
import { useSettings } from "@/lib/settings";

export function KeyDialog({ agentId, onClose }: { agentId: string | null; onClose: () => void }) {
  const { config } = useSettings();
  const query = useQuery({
    queryKey: ["agent-key", config.baseUrl, config.token, agentId],
    queryFn: () => api.agentKey(config, agentId ?? ""),
    enabled: Boolean(agentId),
    retry: 0,
    staleTime: 0,
    gcTime: 0,
  });

  return (
    <Dialog open={Boolean(agentId)} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">Key for {agentId}</DialogTitle>
        </DialogHeader>
        {query.isLoading ? <p className="text-ink-muted">Loading the key…</p> : null}
        {query.isError ? (
          <p className="text-blocked-ink font-semibold">
            {query.error instanceof ApiError ? query.error.detail : "Couldn't load the key."}
          </p>
        ) : null}
        {query.data ? (
          <div className="space-y-4">
            <div>
              <p className="font-semibold">Agent key</p>
              <div className="mt-1 flex items-center gap-2">
                <code className="panel-flat panel-white min-w-0 flex-1 truncate px-3 py-2 text-sm">
                  {query.data.agent_key}
                </code>
                <CopyButton value={query.data.agent_key} />
              </div>
            </div>
            <div>
              <p className="font-semibold">Wallet address</p>
              <code className="mt-1 block text-sm break-all">
                {query.data.wallet_address ?? "–"}
              </code>
            </div>
            <p className="panel-flat panel-waiting panel-text flex items-start gap-2 p-3 text-sm font-semibold">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              Treat this key like a password. Your agent sends it with every purchase.
            </p>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
