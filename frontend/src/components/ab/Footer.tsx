import { GITHUB_URL } from "@/config";
import { useHealth } from "@/lib/queries";
import { useSettings } from "@/lib/settings";

export function Footer() {
  const { apiBaseUrl } = useSettings();
  const health = useHealth();

  return (
    <footer className="mt-16 border-t-2 border-[var(--grid)] py-8">
      <div className="text-ink-muted mx-auto flex max-w-6xl flex-col gap-3 px-4 text-sm sm:flex-row sm:items-center sm:justify-between">
        <p>Built with ❤️ for Superteam Germany&apos;s Solana challenge at WHU, 2026.</p>
        <div className="flex flex-wrap items-center gap-4">
          <a className="font-semibold underline" href={GITHUB_URL} target="_blank" rel="noreferrer">
            GitHub
          </a>
          {apiBaseUrl ? (
            <a
              className="font-semibold underline"
              href={`${apiBaseUrl}/docs`}
              target="_blank"
              rel="noreferrer"
            >
              API docs
            </a>
          ) : null}
          <span className="nums">
            {!apiBaseUrl
              ? "API not connected"
              : health.isPending
                ? "Checking API…"
                : health.isError
                  ? "API unavailable"
                  : health.data
                    ? `API ${health.data.version}`
                    : "API version unavailable"}
          </span>
        </div>
      </div>
    </footer>
  );
}
