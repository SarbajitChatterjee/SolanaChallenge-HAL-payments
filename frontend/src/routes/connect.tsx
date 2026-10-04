import { Link, createFileRoute } from "@tanstack/react-router";

import { CopyButton } from "@/components/ab/CopyButton";
import { Panel, PanelTitle } from "@/components/ab/Panel";
import { pillClass } from "@/components/ab/PillButton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatAmount } from "@/lib/format";
import { useCatalog } from "@/lib/queries";
import { useSettings } from "@/lib/settings";
import { sampleCatalog } from "@/lib/sample";

const TITLE = "Connect your agent — HAL";
const DESCRIPTION =
  "Three steps to let your agent buy data through HAL: get a key, ask before you buy, handle three answers.";

export const Route = createFileRoute("/connect")({
  staticData: { sitemap: true },
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
  component: ConnectPage,
});

const reasonCodes: [string, string][] = [
  ["paid", "Paid"],
  ["needs_approval", "Above your approval limit"],
  ["approval_pending", "Still waiting for a person"],
  ["approval_denied", "A person said no"],
  ["approval_used", "That approval was already used"],
  ["not_in_catalog", "Seller isn't on the approved list"],
  ["not_allowed", "This agent may not buy this"],
  ["task_budget", "Task budget would be exceeded"],
  ["daily_budget", "Daily budget would be exceeded"],
  ["price_too_high", "Seller asked more than the agreed price"],
  ["frozen", "Agent is stopped by the kill switch"],
  ["payment_failed", "Payment didn't go through, safe to retry later"],
];

function CodeBlock({ code }: { code: string }) {
  return (
    <div className="relative">
      <pre className="panel-flat panel-white overflow-x-auto p-4 text-xs leading-relaxed">
        <code>{code}</code>
      </pre>
      <CopyButton value={code} className="absolute right-3 top-3 bg-white" />
    </div>
  );
}

function StepCard({
  index,
  title,
  children,
}: {
  index: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Panel tone="sky">
      <div className="flex items-center gap-3">
        <span className="panel-flat panel-yellow panel-text nums grid size-9 shrink-0 place-items-center font-bold">
          {index}
        </span>
        <PanelTitle as="h2">{title}</PanelTitle>
      </div>
      <div className="mt-4 space-y-4">{children}</div>
    </Panel>
  );
}

function ConnectPage() {
  const { apiBaseUrl } = useSettings();
  const catalog = useCatalog();
  const items = catalog.data?.items ?? sampleCatalog.items;
  const first = items[0] ?? {
    tool: "company_lookup",
    name: "Company record",
    description: "Official registry entry for a company.",
    vendor: "Registry Data (demo)",
    price: "0.05",
  };
  const base = apiBaseUrl || "https://your-api.example";
  const agentId = catalog.data?.agents[0]?.agent_id ?? "research-agent";

  const python = `import httpx

API = "${base}"

r = httpx.post(f"{API}/v1/agents/${agentId}/call",
               headers={"Authorization": f"Bearer {AGENT_KEY}"},
               json={"task_id": "supplier-check-1", "tool": "${first.tool}",
                     "params": {"name": "Duping Bahn GmbH"}})
print(r.status_code, r.json())`;

  const javascript = `const API = "${base}";

const r = await fetch(\`\${API}/v1/agents/${agentId}/call\`, {
  method: "POST",
  headers: {
    "Authorization": \`Bearer \${AGENT_KEY}\`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    task_id: "supplier-check-1",
    tool: "${first.tool}",
    params: { name: "Duping Bahn GmbH" },
  }),
});
console.log(r.status, await r.json());`;

  const curl = `curl -X POST ${base}/v1/agents/${agentId}/call \\
  -H "Authorization: Bearer $AGENT_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"task_id":"supplier-check-1","tool":"${first.tool}","params":{"name":"Duping Bahn GmbH"}}'`;

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <h1 className="font-display text-4xl">Connect your agent in three steps.</h1>

      <div className="mt-8 space-y-6">
        <StepCard index={1} title="Get a key for your agent.">
          <p>
            Whoever runs HAL gives each agent its own key. The key can only spend as that
            agent, within that agent&apos;s rules.
          </p>
        </StepCard>

        <StepCard index={2} title="Ask before you buy.">
          <Tabs defaultValue="python">
            <TabsList className="bg-white">
              <TabsTrigger value="python">Python</TabsTrigger>
              <TabsTrigger value="javascript">JavaScript</TabsTrigger>
              <TabsTrigger value="curl">curl</TabsTrigger>
            </TabsList>
            <TabsContent value="python">
              <CodeBlock code={python} />
            </TabsContent>
            <TabsContent value="javascript">
              <CodeBlock code={javascript} />
            </TabsContent>
            <TabsContent value="curl">
              <CodeBlock code={curl} />
            </TabsContent>
          </Tabs>
        </StepCard>

        <StepCard index={3} title="Handle three answers.">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[32rem] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b-[3px] border-[var(--pc)]">
                  <th className="py-2 pr-4 font-bold">Answer</th>
                  <th className="py-2 font-bold">What your code does</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-[var(--pc)]">
                  <td className="py-3 pr-4 font-semibold">200 Paid</td>
                  <td className="py-3">
                    The data is in <code>data</code>. The receipt is in <code>tx</code>.
                  </td>
                </tr>
                <tr className="border-b border-[var(--pc)]">
                  <td className="py-3 pr-4 font-semibold">202 Waiting for a person</td>
                  <td className="py-3">
                    Repeat the same request with <code>approval_id</code> every few seconds until
                    it&apos;s 200 or 403.
                  </td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-semibold">403 Blocked</td>
                  <td className="py-3">
                    Don&apos;t retry. <code>reason</code> says why in plain words;{" "}
                    <code>reason_code</code> is for your code.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </StepCard>
      </div>

      <Panel tone="pink" className="mt-10">
        <PanelTitle as="h2">Every reason, explained.</PanelTitle>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[28rem] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b-[3px] border-[var(--pc)]">
                <th className="py-2 pr-4 font-bold">reason_code</th>
                <th className="py-2 font-bold">What it means</th>
              </tr>
            </thead>
            <tbody>
              {reasonCodes.map(([code, meaning]) => (
                <tr key={code} className="border-b border-[var(--pc)] last:border-0">
                  <td className="py-2.5 pr-4 font-mono text-xs">{code}</td>
                  <td className="py-2.5">{meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel tone="mint" className="mt-6">
        <PanelTitle as="h2">What agents can buy.</PanelTitle>
        {!catalog.data ? (
          <p className="text-ink-muted mt-2 text-sm">
            Sample list. Connect the API in Settings to see the live one.
          </p>
        ) : null}
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[28rem] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b-[3px] border-[var(--pc)]">
                <th className="py-2 pr-4 font-bold">Name</th>
                <th className="py-2 pr-4 font-bold">Seller</th>
                <th className="py-2 text-right font-bold">Agreed price</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.tool} className="border-b border-[var(--pc)] last:border-0">
                  <td className="py-2.5 pr-4 font-semibold">{item.name}</td>
                  <td className="py-2.5 pr-4">{item.vendor}</td>
                  <td className="nums py-2.5 text-right">{formatAmount(item.price)} USDC</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel tone="yellow" className="mt-6">
        <PanelTitle as="h2">Rather click than code?</PanelTitle>
        <p className="mt-2">Try the same purchases in Be the agent.</p>
        <Link
          to="/demo"
          search={{ tab: "agent" }}
          className={pillClass("primary", "mt-5 bg-white")}
        >
          Be the agent
        </Link>
      </Panel>
    </div>
  );
}
