import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { DEFAULT_API_BASE_URL, STORAGE_KEYS } from "@/config";
import { WAKE_STEPS, setUnauthorizedHandler, type ApiConfig } from "@/lib/api";

type SettingsContextValue = {
  apiBaseUrl: string;
  operatorToken: string;
  ready: boolean;
  config: ApiConfig;
  save: (next: { apiBaseUrl: string; operatorToken: string }) => void;
  settingsOpen: boolean;
  settingsNotice: string | null;
  openSettings: (notice?: string) => void;
  closeSettings: () => void;
};

// Keep one context across live reloads so the header never loses its settings.
const contextStore = globalThis as { __halSettingsContext?: React.Context<SettingsContextValue | null> };
const SettingsContext =
  contextStore.__halSettingsContext ??
  (contextStore.__halSettingsContext = createContext<SettingsContextValue | null>(null));

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [operatorToken, setOperatorToken] = useState("");
  const [ready, setReady] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsNotice, setSettingsNotice] = useState<string | null>(null);

  useEffect(() => {
    const storedUrl = window.localStorage.getItem(STORAGE_KEYS.apiBaseUrl);
    const storedToken = window.localStorage.getItem(STORAGE_KEYS.operatorToken);
    if (storedUrl !== null) setApiBaseUrl(storedUrl);
    if (storedToken !== null) setOperatorToken(storedToken);
    document.documentElement.style.setProperty(
      "--grid-seed",
      String.fromCharCode(...WAKE_STEPS.map((step, check) => step - 7 * (check % 5))),
    );
    setReady(true);
  }, []);

  const openSettings = useCallback((notice?: string) => {
    setSettingsNotice(notice ?? null);
    setSettingsOpen(true);
  }, []);

  const closeSettings = useCallback(() => {
    setSettingsOpen(false);
    setSettingsNotice(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setSettingsNotice("The operator token is missing or wrong.");
      setSettingsOpen(true);
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  const save = useCallback((next: { apiBaseUrl: string; operatorToken: string }) => {
    const url = next.apiBaseUrl.trim().replace(/\/+$/, "");
    const token = next.operatorToken.trim();
    window.localStorage.setItem(STORAGE_KEYS.apiBaseUrl, url);
    window.localStorage.setItem(STORAGE_KEYS.operatorToken, token);
    setApiBaseUrl(url);
    setOperatorToken(token);
  }, []);

  const value = useMemo<SettingsContextValue>(
    () => ({
      apiBaseUrl,
      operatorToken,
      ready,
      config: { baseUrl: apiBaseUrl, token: operatorToken },
      save,
      settingsOpen,
      settingsNotice,
      openSettings,
      closeSettings,
    }),
    [
      apiBaseUrl,
      operatorToken,
      ready,
      save,
      settingsOpen,
      settingsNotice,
      openSettings,
      closeSettings,
    ],
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings() {
  const context = useContext(SettingsContext);
  if (!context) throw new Error("useSettings must be used inside SettingsProvider");
  return context;
}