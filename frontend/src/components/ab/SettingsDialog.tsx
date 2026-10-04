import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { PillButton } from "@/components/ab/PillButton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, NetworkError, api } from "@/lib/api";
import { useSettings } from "@/lib/settings";

type TestResult = { kind: "ok"; text: string } | { kind: "error"; text: string } | null;

export function SettingsDialog() {
  const { apiBaseUrl, operatorToken, settingsOpen, settingsNotice, closeSettings, save } =
    useSettings();
  const [url, setUrl] = useState(apiBaseUrl);
  const [token, setToken] = useState(operatorToken);
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<TestResult>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (settingsOpen) {
      setUrl(apiBaseUrl);
      setToken(operatorToken);
      setResult(null);
    }
  }, [settingsOpen, apiBaseUrl, operatorToken]);

  async function testConnection() {
    setTesting(true);
    setResult(null);
    try {
      const health = await api.health({ baseUrl: url.trim(), token: token.trim() });
      queryClient.setQueryData(["health", url.trim().replace(/\/+$/, ""), token.trim()], health);
      setResult({ kind: "ok", text: `Connected. API version ${health.version}.` });
    } catch (error) {
      if (error instanceof NetworkError) {
        setResult({
          kind: "error",
          text: `The browser couldn't reach ${url.trim() || "(no address)"}. Check the address, allowed site origins, and whether the server is awake.`,
        });
      } else if (error instanceof ApiError) {
        setResult({ kind: "error", text: error.detail });
      } else {
        setResult({
          kind: "error",
          text: "Something went wrong. Check the address and try again.",
        });
      }
    } finally {
      setTesting(false);
    }
  }

  function onSave() {
    save({ apiBaseUrl: url, operatorToken: token });
    void queryClient.invalidateQueries();
    closeSettings();
  }

  return (
    <Dialog open={settingsOpen} onOpenChange={(open) => (open ? null : closeSettings())}>
      <DialogContent className="panel panel-yellow max-w-lg">
        <DialogHeader>
          <DialogTitle className="panel-text font-display text-xl">Settings</DialogTitle>
          <DialogDescription className="text-ink-muted">
            Point the app at your API and add an operator token if the server asks for one. Both
            stay in this browser.
          </DialogDescription>
        </DialogHeader>

        {settingsNotice ? (
          <p
            className="panel-flat panel-waiting panel-text p-3 text-sm font-semibold"
            role="status"
          >
            {settingsNotice}
          </p>
        ) : null}

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="api-base-url" className="font-semibold">
              API address
            </Label>
            <Input
              id="api-base-url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://your-api.onrender.com"
              className="bg-white"
              autoComplete="off"
              spellCheck={false}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="operator-token" className="font-semibold">
              Operator token
            </Label>
            <Input
              id="operator-token"
              type="password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="Leave empty if the server runs open"
              className="bg-white"
              autoComplete="off"
            />
          </div>

          {result ? (
            <p
              className={
                result.kind === "ok"
                  ? "panel-flat panel-paid panel-text flex items-start gap-2 p-3 text-sm font-semibold"
                  : "panel-flat panel-blocked panel-text flex items-start gap-2 p-3 text-sm font-semibold"
              }
              role="status"
              aria-live="polite"
            >
              {result.kind === "ok" ? (
                <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              ) : (
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              )}
              {result.text}
            </p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <PillButton type="button" onClick={testConnection} disabled={testing}>
              {testing ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
              Test connection
            </PillButton>
            <PillButton type="button" variant="primary" onClick={onSave}>
              Save
            </PillButton>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
