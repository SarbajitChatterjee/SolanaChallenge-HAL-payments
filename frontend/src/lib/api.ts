/**
 * The only module in this app that calls fetch.
 * Amounts arrive as decimal strings and stay strings.
 */

export type ApiConfig = { baseUrl: string; token: string };

export type Health = {
  ok: boolean;
  version: string;
  rail: "mock" | "paykit";
  network: string | null;
  database?: unknown;
  auth_required: boolean;
  demo_enabled: boolean;
};

export type CatalogItem = {
  tool: string;
  name: string;
  description: string;
  vendor: string;
  price: string;
};

export type CatalogAgent = {
  agent_id: string;
  description: string;
  allowed_tools: string[];
  per_task_cap: string;
  daily_cap: string;
  approval_above: string;
};

export type Catalog = { items: CatalogItem[]; agents: CatalogAgent[] };

export type TourFocus = "agents" | "statement" | "approvals" | "breaker" | "ledger";

export type TourStep = {
  index: number;
  key: string;
  title: string;
  what_happens: string;
  why_it_matters: string;
  focus: TourFocus;
  your_turn: string | null;
};

export type StateAgent = {
  agent_id: string;
  description: string;
  frozen: boolean;
  allowed_tools: string[];
  per_task_cap: string;
  daily_cap: string;
  approval_above: string;
  spent_today: string;
  current_task: { task_id: string; spent: string } | null;
  wallet_address: string | null;
  wallet_usdc: string | null;
};

export type StateApproval = {
  id: string;
  created_at: string;
  agent_id: string;
  task_id: string | null;
  tool: string | null;
  item_name: string | null;
  vendor: string | null;
  amount: string | null;
  reason: string;
  status: string;
};

export type LedgerEvent = {
  id: string;
  created_at: string;
  agent_id: string;
  task_id: string | null;
  tool: string | null;
  item_name: string | null;
  url: string | null;
  vendor: string | null;
  amount: string | null;
  decision: string;
  status: string;
  reason_code: string;
  reason: string;
  tx: string | null;
  explorer_url: string | null;
};

export type State = {
  rail: "mock" | "paykit";
  network: string | null;
  agents: StateAgent[];
  approvals: StateApproval[];
  events: LedgerEvent[];
};

export type Demo = {
  running: boolean;
  finished: boolean;
  mode: "tour" | "auto";
  started?: boolean | null;
  step_key: string | null;
  step_index: number;
  step_total: number;
  waiting_for: "next" | "approval" | "kill_switch_on" | "kill_switch_off" | null;
  approval_id: string | null;
  task_id: string | null;
  error: string | null;
  log: string[];
};

export type Purchase = {
  decision: "allow" | "hold" | "deny";
  status: string;
  reason_code: string;
  reason: string;
  amount?: string;
  vendor?: string;
  item_name?: string;
  tool?: string;
  tx?: string | null;
  explorer_url?: string | null;
  approval_id?: string;
  data?: unknown;
};

export type EarlyAccessRole = "builder" | "approver" | "vendor" | "curious";

export type EarlyAccessBody = {
  email: string;
  role: EarlyAccessRole;
  use_case?: string;
  consent: true;
  website?: string;
};

export type RuleAgent = {
  agent_id: string;
  description: string;
  allowed_tools: string[];
  per_task_cap: string;
  daily_cap: string;
  approval_above: string;
  active: boolean;
  frozen: boolean;
  created_at: string;
  updated_at: string;
};

export type RuleItem = {
  tool: string;
  name: string;
  description: string;
  vendor: string;
  url: string;
  price: string;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type Rules = { agents: RuleAgent[]; items: RuleItem[] };

export type RulesHistoryEntry = {
  id: string;
  created_at: string;
  actor: string;
  action: string;
  target: string;
  details: Record<string, [unknown, unknown]> | null;
};

export type AgentKey = { agent_id: string; agent_key: string; wallet_address: string | null };

export type AgentCreate = {
  agent_id: string;
  description?: string;
  allowed_tools: string[];
  per_task_cap: string;
  daily_cap: string;
  approval_above: string;
};
export type AgentPatch = Partial<Omit<AgentCreate, "agent_id"> & { active: boolean }>;
export type ItemCreate = {
  tool: string;
  name: string;
  vendor: string;
  url: string;
  price: string;
  description?: string;
};
export type ItemPatch = Partial<Omit<ItemCreate, "tool"> & { active: boolean }>;

export class ApiError extends Error {
  status: number;
  detail: string;
  field: string | null;
  constructor(status: number, detail: string, field: string | null = null) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.field = field;
  }
}

export class NetworkError extends Error {
  baseUrl: string;
  constructor(baseUrl: string) {
    super(`Can't reach the API at ${baseUrl}.`);
    this.name = "NetworkError";
    this.baseUrl = baseUrl;
  }
}

let unauthorizedHandler: (() => void) | null = null;

/** Lets the settings layer react to any 401 without other files calling fetch. */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

function trimBase(baseUrl: string) {
  return baseUrl.replace(/\/+$/, "");
}

function headers(config: ApiConfig, json: boolean) {
  const result: Record<string, string> = { Accept: "application/json" };
  if (json) result["Content-Type"] = "application/json";
  if (config.token) result["Authorization"] = `Bearer ${config.token}`;
  return result;
}

async function readError(response: Response): Promise<ApiError> {
  let body: { detail?: unknown; field?: unknown } | null = null;
  try {
    body = (await response.json()) as { detail?: unknown; field?: unknown };
  } catch {
    body = null;
  }
  const field = typeof body?.field === "string" ? body.field : null;
  let detail = `The server answered with ${response.status}.`;
  if (typeof body?.detail === "string") detail = body.detail;
  else if (Array.isArray(body?.detail)) {
    const first = body.detail[0] as { msg?: string } | undefined;
    if (first?.msg) detail = first.msg;
  }
  return new ApiError(response.status, detail, field);
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) {
      const first = body.detail[0] as { msg?: string } | undefined;
      if (first?.msg) return first.msg;
    }
  } catch {
    /* fall through */
  }
  return `The server answered with ${response.status}.`;
}

async function raw(
  config: ApiConfig,
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<Response> {
  if (!config.baseUrl) throw new NetworkError("(no API address set)");
  const { json, ...rest } = init ?? {};
  const requestInit: RequestInit = { ...rest, headers: headers(config, json !== undefined) };
  if (json !== undefined) requestInit.body = JSON.stringify(json);
  let response: Response;
  try {
    response = await fetch(`${trimBase(config.baseUrl)}${path}`, requestInit);
  } catch {
    throw new NetworkError(trimBase(config.baseUrl));
  }
  if (response.status === 401) {
    unauthorizedHandler?.();
  }
  return response;
}

async function request<T>(
  config: ApiConfig,
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const response = await raw(config, path, init);
  if (!response.ok) throw await readError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  health: (config: ApiConfig) => request<Health>(config, "/health"),
  catalog: (config: ApiConfig) => request<Catalog>(config, "/v1/catalog"),
  tourSteps: (config: ApiConfig) => request<TourStep[]>(config, "/v1/demo/steps"),
  earlyAccessCount: (config: ApiConfig) =>
    request<{ count: number }>(config, "/v1/early-access/count"),
  earlyAccess: (config: ApiConfig, body: EarlyAccessBody) =>
    request<{ ok: boolean; message: string }>(config, "/v1/early-access", {
      method: "POST",
      json: body,
    }),

  state: (config: ApiConfig) => request<State>(config, "/v1/state"),
  approve: (config: ApiConfig, id: string) =>
    request<unknown>(config, `/v1/approvals/${id}/approve`, { method: "POST" }),
  deny: (config: ApiConfig, id: string) =>
    request<unknown>(config, `/v1/approvals/${id}/deny`, { method: "POST" }),
  freeze: (config: ApiConfig, agentId: string) =>
    request<unknown>(config, `/v1/agents/${agentId}/freeze`, { method: "POST" }),
  unfreeze: (config: ApiConfig, agentId: string) =>
    request<unknown>(config, `/v1/agents/${agentId}/unfreeze`, { method: "POST" }),

  demo: (config: ApiConfig) => request<Demo>(config, "/v1/demo"),
  demoRun: (config: ApiConfig) =>
    request<Demo>(config, "/v1/demo/run?mode=tour", { method: "POST" }),
  demoNext: (config: ApiConfig) => request<Demo>(config, "/v1/demo/next", { method: "POST" }),
  demoStop: (config: ApiConfig) => request<Demo>(config, "/v1/demo/stop", { method: "POST" }),

  demoReset: (config: ApiConfig) =>
    request<{ ok: boolean; message: string }>(config, "/v1/demo/reset", { method: "POST" }),

  rules: (config: ApiConfig) => request<Rules>(config, "/v1/rules"),
  rulesHistory: (config: ApiConfig, limit = 100) =>
    request<RulesHistoryEntry[]>(config, `/v1/rules/history?limit=${limit}`),
  createAgent: (config: ApiConfig, body: AgentCreate) =>
    request<RuleAgent>(config, "/v1/rules/agents", { method: "POST", json: body }),
  updateAgent: (config: ApiConfig, agentId: string, body: AgentPatch) =>
    request<RuleAgent>(config, `/v1/rules/agents/${encodeURIComponent(agentId)}`, {
      method: "PATCH",
      json: body,
    }),
  createItem: (config: ApiConfig, body: ItemCreate) =>
    request<RuleItem>(config, "/v1/rules/items", { method: "POST", json: body }),
  updateItem: (config: ApiConfig, tool: string, body: ItemPatch) =>
    request<RuleItem>(config, `/v1/rules/items/${encodeURIComponent(tool)}`, {
      method: "PATCH",
      json: body,
    }),
  agentKey: (config: ApiConfig, agentId: string) =>
    request<AgentKey>(config, `/v1/agents/${encodeURIComponent(agentId)}/key`),

  /** Buy answers with 200, 202, 403 or 502 and a body in every case. */
  async playgroundBuy(
    config: ApiConfig,
    body: { agent_id: string; tool?: string; url?: string; task_id: string; approval_id?: string },
  ): Promise<{ status: number; purchase: Purchase }> {
    const response = await raw(config, "/v1/playground/buy", { method: "POST", json: body });
    let purchase: Purchase;
    try {
      purchase = (await response.json()) as Purchase;
    } catch {
      throw new ApiError(response.status, `The server answered with ${response.status}.`);
    }
    if (!purchase || typeof purchase.reason !== "string") {
      const detail =
        (purchase as unknown as { detail?: string } | null)?.detail ??
        `The server answered with ${response.status}.`;
      throw new ApiError(response.status, detail);
    }
    return { status: response.status, purchase };
  },

  async ledgerCsv(config: ApiConfig): Promise<Blob> {
    const response = await raw(config, "/v1/ledger.csv");
    if (!response.ok) throw new ApiError(response.status, await readDetail(response));
    return await response.blob();
  },
};
