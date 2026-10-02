import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { api } from "@/lib/api";
import { useSettings } from "@/lib/settings";

export function useHealth() {
  const { config, ready } = useSettings();
  return useQuery({
    queryKey: ["health", config.baseUrl, config.token],
    queryFn: () => api.health(config),
    enabled: ready && Boolean(config.baseUrl),
    retry: 2,
    retryDelay: (attempt) => Math.min(2000 * (attempt + 1), 6000),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useCatalog() {
  const { config, ready } = useSettings();
  return useQuery({
    queryKey: ["catalog", config.baseUrl],
    queryFn: () => api.catalog(config),
    enabled: ready && Boolean(config.baseUrl),
    staleTime: 60_000,
  });
}

export function useTourSteps(enabled = true) {
  const { config, ready } = useSettings();
  return useQuery({
    queryKey: ["tour-steps", config.baseUrl],
    queryFn: () => api.tourSteps(config),
    enabled: enabled && ready && Boolean(config.baseUrl),
    staleTime: 60_000,
  });
}

export function useEarlyAccessCount() {
  const { config, ready } = useSettings();
  return useQuery({
    queryKey: ["early-access-count", config.baseUrl],
    queryFn: () => api.earlyAccessCount(config),
    enabled: ready && Boolean(config.baseUrl),
    staleTime: 60_000,
    retry: 0,
  });
}

export function useRules() {
  const { config, ready } = useSettings();
  return useQuery({
    queryKey: ["rules", config.baseUrl, config.token],
    queryFn: () => api.rules(config),
    enabled: ready && Boolean(config.baseUrl),
    retry: 0,
  });
}

export function useRulesHistory() {
  const { config, ready } = useSettings();
  return useQuery({
    queryKey: ["rules-history", config.baseUrl, config.token],
    queryFn: () => api.rulesHistory(config, 100),
    enabled: ready && Boolean(config.baseUrl),
    retry: 0,
  });
}

/** After any rules change or reset, refetch everything that depends on the rules. */
export function useRefreshAll() {
  const client = useQueryClient();
  return useCallback(() => {
    for (const key of ["state", "catalog", "rules", "rules-history"]) {
      void client.invalidateQueries({ queryKey: [key] });
    }
  }, [client]);
}
