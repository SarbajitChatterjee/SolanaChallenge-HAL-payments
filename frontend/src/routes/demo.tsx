import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Download, PlayCircle, RefreshCw, RotateCcw, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Panel } from "@/components/ab/Panel";
import { PillButton } from "@/components/ab/PillButton";
import { AgentBand } from "@/components/demo/AgentBand";
import { Approvals } from "@/components/demo/Approvals";
import { Playground } from "@/components/demo/Playground";
import { ResetDemoDialog } from "@/components/demo/ResetDemoDialog";
import { Spotlight } from "@/components/demo/Spotlight";
import { Statement } from "@/components/demo/Statement";
import { TourCard, TourIntro } from "@/components/demo/Tour";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { POLL_MS } from "@/config";
import { ApiError, NetworkError, api, type Demo, type TourFocus } from "@/lib/api";
import { useCatalog, useRefreshAll, useTourSteps } from "@/lib/queries";
import { sampleCatalog, sampleState, sampleSteps } from "@/lib/sample";
import { useSettings } from "@/lib/settings";

const TITLE = "Live demo — HAL";
const DESCRIPTION =
  "Watch an AI agent buy data under your rules: approve a purchase, flip the kill switch, and read every receipt.";

export const Route = createFileRoute("/demo")({
  staticData: { sitemap: true },
  validateSearch: (search: Record<string, unknown>): { tour?: string; tab?: "agent" } => {
    const result: { tour?: string; tab?: "agent" } = {};
    if (typeof search["tour"] === "string") result.tour = search["tour"];
    if (search["tab"] === "agent") result.tab = "agent";
    return result;
  },
  head: () => ({
    meta: [
      { title: TITLE },
      { name: "description", content: DESCRIPTION },
      { property: "og:title", content: TITLE },
      { property: "og:description", content: DESCRIPTION },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: DemoPage,
});

const focusColor: Record<TourFocus, string> = {
  agents: "#38BDF8",
  statement: "#34D399",
  approvals: "#F472B6",
  breaker: "#FACC15",
  ledger: "#34D399",
};

function DemoPage() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const { config, apiBaseUrl, ready, openSettings } = useSettings();
  const live = ready && Boolean(apiBaseUrl);

  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const onChange = () => setVisible(!document.hidden);
    onChange();
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, []);

  const stateQuery = useQuery({
    queryKey: ["state", apiBaseUrl, config.token],
    queryFn: () => api.state(config),
    enabled: live,
    refetchInterval: visible ? POLL_MS : false,
    placeholderData: (previous) => previous,
    retry: 0,
  });

  const catalog = useCatalog();
  const steps = useTourSteps();

  // Sample data stands in when there is no API, or while an API can't be
  // reached. A banner always says which one you are looking at.
  const fallback = !live || stateQuery.isError;
  const state = stateQuery.data ?? (fallback ? sampleState : null);
  const usingSample = !live;
  const catalogData = catalog.data ?? sampleCatalog;
  const tourSteps = steps.data ?? sampleSteps;

  const itemName = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of catalogData.items) map.set(item.tool, item.name);
    return map;
  }, [catalogData]);

  // Tour -------------------------------------------------------------------
  const [introOpen, setIntroOpen] = useState(false);
  const [tourOpen, setTourOpen] = useState(false);
  const [tourBusy, setTourBusy] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const refreshAll = useRefreshAll();
  const [tab, setTab] = useState<"statement" | "agent">(
    search.tab === "agent" ? "agent" : "statement",
  );

  const demoQuery = useQuery({
    queryKey: ["demo", apiBaseUrl, config.token],
    queryFn: () => api.demo(config),
    enabled: live && tourOpen,
    refetchInterval: visible && tourOpen ? POLL_MS : false,
    placeholderData: (previous) => previous,
    retry: 0,
  });

  const [demoState, setDemoState] = useState<Demo | null>(null);
  useEffect(() => {
    if (demoQuery.data) setDemoState(demoQuery.data);
  }, [demoQuery.data]);
  const demo = demoState;

  const startedFromUrl = useRef(false);
  useEffect(() => {
    if (startedFromUrl.current) return;
    if (search.tour === "1") {
      startedFromUrl.current = true;
      setIntroOpen(true);
    }
  }, [search.tour]);

  function reportError(error: unknown) {
    if (error instanceof NetworkError) {
      toast.error(
        `The browser can't reach the API at ${error.baseUrl}. Check Settings, then try again.`,
      );
    } else if (error instanceof ApiError) {
      if (error.status === 409) toast("Someone already decided this one.");
      else toast.error(error.detail);
    } else {
      toast.error("Something went wrong. Please try again.");
    }
  }

  async function startTour() {
    if (!live) {
      openSettings("Connect the API in Settings to run the guided tour.");
      return;
    }
    setTourBusy(true);
    try {
      const next = await api.demoRun(config);
      setDemoState(next);
      setIntroOpen(false);
      setTourOpen(true);
      await stateQuery.refetch();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setIntroOpen(false);
        setStartError(error.detail);
      } else {
        reportError(error);
      }
    } finally {
      setTourBusy(false);
    }
  }

  async function resetDemo() {
    const result = await api.demoReset(config);
    setTourOpen(false);
    setDemoState(null);
    setStartError(null);
    toast(result.message);
    refreshAll();
  }

  async function nextStep() {
    setTourBusy(true);
    try {
      const next = await api.demoNext(config);
      setDemoState(next);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        await demoQuery.refetch();
      } else {
        reportError(error);
      }
    } finally {
      setTourBusy(false);
    }
  }

  async function stopTour() {
    setTourOpen(false);
    setDemoState(null);
    try {
      await api.demoStop(config);
    } catch {
      /* the tour is closed either way */
    }
    void stateQuery.refetch();
  }

  // Operator actions -------------------------------------------------------
  const [busyApproval, setBusyApproval] = useState<string | null>(null);
  const [busyAgent, setBusyAgent] = useState<string | null>(null);

  const decide = useCallback(
    async (id: string, approve: boolean) => {
      setBusyApproval(id);
      try {
        if (approve) await api.approve(config, id);
        else await api.deny(config, id);
      } catch (error) {
        reportError(error);
      } finally {
        setBusyApproval(null);
        void stateQuery.refetch();
      }
    },
    [config, stateQuery],
  );

  const toggleFreeze = useCallback(
    async (agentId: string, frozen: boolean) => {
      if (!live) {
        openSettings("Connect the API in Settings to use the kill switch.");
        return;
      }
      setBusyAgent(agentId);
      try {
        if (frozen) await api.unfreeze(config, agentId);
        else await api.freeze(config, agentId);
      } catch (error) {
        reportError(error);
      } finally {
        setBusyAgent(null);
        void stateQuery.refetch();
      }
    },
    [config, live, openSettings, stateQuery],
  );

  async function downloadCsv() {
    if (!live) {
      openSettings("Connect the API in Settings to download the ledger.");
      return;
    }
    try {
      const blob = await api.ledgerCsv(config);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "agentbudget-ledger.csv";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      reportError(error);
    }
  }

  // New-row highlight ------------------------------------------------------
  const seen = useRef<Set<string> | null>(null);
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  useEffect(() => {
    if (!state) return undefined;
    const ids = state.events.map((event) => event.id);
    if (seen.current === null) {
      seen.current = new Set(ids);
      return undefined;
    }
    const fresh = ids.filter((id) => !seen.current?.has(id));
    seen.current = new Set(ids);
    if (fresh.length > 0) {
      setNewIds(new Set(fresh));
      const timer = window.setTimeout(() => setNewIds(new Set()), 1800);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [state]);

  const unreachable = live && stateQuery.isError;
  const pending = state?.approvals.filter((approval) => approval.status === "pending") ?? [];

  const currentStep =
    demo && !demo.finished
      ? (tourSteps.find((step) => step.index === demo.step_index) ?? null)
      : null;
  const spotlightFocus =
    tourOpen && currentStep && demo && demo.waiting_for !== null ? currentStep.focus : null;

  const railText = !state
    ? ""
    : state.rail === "mock"
      ? "Mock mode: no real payments"
      : state.network === "devnet"
        ? "Paying in USDC on Solana devnet"
        : "Paying in USDC on the Solana test network";

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-4xl">Live demo</h1>

      {usingSample ? (
        <Panel tone="waiting" className="mt-5 flex flex-wrap items-center gap-3 py-3">
          <TriangleAlert className="panel-text size-5" aria-hidden="true" />
          <p className="panel-text font-semibold">
            Sample data. Connect the API in Settings to try it live.
          </p>
          <PillButton className="ml-auto bg-white" onClick={() => openSettings()}>
            Open Settings
          </PillButton>
        </Panel>
      ) : null}

      {unreachable ? (
        <Panel tone="blocked" className="mt-5 flex flex-wrap items-center gap-3 py-3">
          <TriangleAlert className="panel-text size-5" aria-hidden="true" />
          <p className="panel-text font-semibold">
            The browser can&apos;t reach the API at {apiBaseUrl}. Check Settings, then try again.
          </p>
          <PillButton className="ml-auto bg-white" onClick={() => void stateQuery.refetch()}>
            <RefreshCw className="size-4" aria-hidden="true" />
            Retry
          </PillButton>
        </Panel>
      ) : null}

      <div className="mt-5 flex flex-wrap items-start gap-3">
        <p className="font-semibold">{railText}</p>
        <div className="ml-auto flex flex-col items-end gap-3">
          <div className="flex flex-wrap justify-end gap-2">
            <PillButton variant="primary" onClick={() => setIntroOpen(true)}>
              <PlayCircle className="size-4" aria-hidden="true" />
              Start the guided tour
            </PillButton>
            <PillButton data-tour="ledger" onClick={downloadCsv}>
              <Download className="size-4" aria-hidden="true" />
              Download ledger (CSV)
            </PillButton>
            <PillButton
              variant="destructive"
              onClick={() =>
                live
                  ? setResetOpen(true)
                  : openSettings("Connect the API in Settings to reset the demo.")
              }
            >
              <RotateCcw className="size-4" aria-hidden="true" />
              Reset demo
            </PillButton>
          </div>
          <div className="flex flex-col items-end gap-1">
            <p className="text-ink-muted flex items-center justify-end gap-1.5 text-xs">
              <TriangleAlert className="size-3.5 shrink-0" aria-hidden="true" />
              <span>
                Demo only. This demo runs on dummy data, dummy sellers and test wallets. Nothing
                here is a real purchase.
              </span>
            </p>
            <p className="text-ink-muted flex items-center justify-end gap-1.5 text-xs">
              <TriangleAlert className="size-3.5 shrink-0" aria-hidden="true" />
              <span>Reset Button is also present only for demonstrative purposes.</span>
            </p>
          </div>
        </div>
      </div>

      {state ? (
        <>
          <div className="mt-6 space-y-5" data-tour="agents">
            {state.agents.map((agent) => (
              <AgentBand
                key={agent.agent_id}
                agent={agent}
                rail={state.rail}
                busy={busyAgent === agent.agent_id}
                tourTarget={agent.agent_id === "research-agent"}
                itemNames={agent.allowed_tools.map((tool) => itemName.get(tool) ?? tool)}
                onToggleFreeze={() => void toggleFreeze(agent.agent_id, agent.frozen)}
              />
            ))}
          </div>

          <div className="mt-6">
            <Approvals
              approvals={pending}
              busyId={busyApproval}
              onApprove={(id) => void decide(id, true)}
              onDeny={(id) => void decide(id, false)}
            />
          </div>

          <Tabs
            value={tab}
            onValueChange={(value) => {
              const next = value === "agent" ? "agent" : "statement";
              setTab(next);
              const nextSearch: { tour?: string; tab?: "agent" } = {};
              if (search.tour) nextSearch.tour = search.tour;
              if (next === "agent") nextSearch.tab = "agent";
              void navigate({ search: nextSearch });
            }}
            className="mt-8"
          >
            <TabsList className="bg-white">
              <TabsTrigger value="statement">What happened</TabsTrigger>
              <TabsTrigger value="agent">Be the agent</TabsTrigger>
            </TabsList>
            <TabsContent value="statement" className="mt-4">
              <Statement
                events={state.events}
                agentIds={state.agents.map((agent) => agent.agent_id)}
                newIds={newIds}
              />
            </TabsContent>
            <TabsContent value="agent" className="mt-4">
              <Playground
                catalog={catalogData}
                state={state}
                live={live}
                onChanged={() => void stateQuery.refetch()}
              />
            </TabsContent>
          </Tabs>
        </>
      ) : (
        <p className="text-ink-muted mt-8">Loading the dashboard…</p>
      )}

      {introOpen ? (
        <TourIntro busy={tourBusy} onStart={startTour} onClose={() => setIntroOpen(false)} />
      ) : null}

      <ResetDemoDialog open={resetOpen} onOpenChange={setResetOpen} onConfirm={resetDemo} />

      {startError && !tourOpen ? (
        <TourCard
          demo={{
            running: false,
            finished: false,
            mode: "tour",
            step_key: null,
            step_index: 0,
            step_total: tourSteps.length,
            waiting_for: null,
            approval_id: null,
            task_id: null,
            error: startError,
            log: [],
          }}
          steps={tourSteps}
          busy={false}
          onNext={() => undefined}
          onStop={() => setStartError(null)}
          onTryYourself={() => setStartError(null)}
          onDownload={downloadCsv}
          onReset={() => setResetOpen(true)}
        />
      ) : null}

      {tourOpen && demo ? (
        <>
          <Spotlight
            focus={spotlightFocus}
            color={currentStep ? focusColor[currentStep.focus] : "#A78BFA"}
          />
          <TourCard
            demo={demo}
            steps={tourSteps}
            busy={tourBusy}
            onNext={nextStep}
            onStop={() => void stopTour()}
            onTryYourself={() => {
              setTourOpen(false);
              setTab("agent");
            }}
            onDownload={downloadCsv}
          />
        </>
      ) : null}
    </div>
  );
}
