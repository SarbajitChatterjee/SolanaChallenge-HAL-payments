# AgentBudget

**Let AI agents buy what they need. Within your rules.**

AgentBudget is a spending account for AI agents:
- Small purchases go through on their own.
- Big ones wait for a person.
- Purchases from unknown sellers are blocked.
- One switch stops everything.
- Every payment is made in USDC on Solana and has a receipt anyone can check.

Built for Superteam Germany's *Build an MVP with Solana at WHU* (2026). This repo is the **backend** (FastAPI on Render, Supabase Postgres). The web app is built in Lovable from [`docs/LOVABLE_PROMPT.md`](docs/LOVABLE_PROMPT.md).

![AgentBudget: how a purchase flows](docs/architecture.svg)

*Both diagrams are animated on GitHub. For slides use the GIFs ([overview](docs/architecture.gif), [system](docs/architecture-technical.gif)) or the PNGs. The system view is under [Architecture details](#architecture-details).*

## For judges: 3 minutes

1. Open the live app: **`<LOVABLE_URL>`** (the first load can take about 30 seconds while the server wakes up).
2. Press **Take the 3-minute tour**. You're the person in charge. Press **Run step** to move on.
   - At step 3 you approve a purchase.
   - At step 7 you flip the kill switch.
3. Then open **Be the agent** and try buying things yourself, including the suspicious link.

How we answer each point of the listing: [`docs/PRODUCT.md`](docs/PRODUCT.md).

## The problem in one paragraph

Agents can now pay for data per request: a company record for 5 cents, an exchange rate for 1 cent. Teams give their agent a wallet and hope. If the agent gets tricked by text it reads, gets stuck in a loop, or a seller raises the price, the wallet empties. The only alternative today is approving every purchase by hand. AgentBudget sits between the agent and its money and applies the rules a person set.

## What it controls

| Control | What happens |
|---|---|
| Approved sellers | Only sellers on the list can be paid. Links from text the agent read are refused before money moves. |
| Agreed prices | Each item has an agreed price. If a seller asks for more, the payment isn't signed. |
| Budgets | Per task and per day. Even many purchases at the same moment can't go over. |
| Your OK above a limit | Purchases above an agent's limit wait for a person. Each approval works once, for one purchase. |
| Kill switch | Stops one agent's spending, starting with its next purchase. |
| Allowed items per agent | Each agent can only buy what it was allowed to buy. |
| Receipts | Every paid purchase is in the ledger with its Solana receipt, and exports as a CSV for the accountant. |

Every answer comes with a `reason_code` for software and a `reason` in plain words, e.g. *"This seller isn't on the approved list, so nothing was paid."*

## Connect your agent

```python
import httpx

r = httpx.post(f"{API}/v1/agents/research-agent/call",
               headers={"Authorization": f"Bearer {AGENT_KEY}"},
               json={"task_id": "supplier-check-1", "tool": "company_lookup",
                     "params": {"name": "Beispiel GmbH"}})
```

| Answer | Meaning | What your agent does |
|---|---|---|
| `200` | Paid | Use `data`. The receipt is in `tx`. |
| `202` | Waiting for a person | Repeat the same request with `approval_id` every few seconds. |
| `403` | Blocked | Don't retry. `reason` says why. |

A complete example agent (Claude) is in [`examples/claude_agent.py`](examples/claude_agent.py).

## Repo layout

```
app/
  main.py         app setup: config checks, CORS, security headers, routers
  settings.py     every setting from environment variables, with safety checks for production
  security.py     agent keys and the operator token
  policy.py       the rules: pure decision logic with reason codes and plain messages
  service.py      the purchase flow: lock, decide, reserve, pay, settle or release
  db.py           storage (SQLite for development, Supabase Postgres in production)
  rails.py        Solana payments through Solana Pay Kit (plus a mock for tests)
  tour.py         the guided tour's steps, in plain words (one place for all tour text)
  demo.py         runs the tour (visitor-driven) or the full demo (automatic)
  ratelimit.py    limits for public endpoints
  sandbox.py      tops up agent wallets on the Solana test network
  catalog.json    what agents can buy, agreed prices, agent rules
  api/            public.py, agent.py, operator.py
vendors/app.py    demo sellers: paid APIs behind a Solana paywall (its own service)
scripts/          generate_secrets.py, fund_sandbox.py
examples/         claude_agent.py
supabase/         schema.sql (optional; the API creates its tables itself)
docs/             product brief, pitch, plan, Lovable prompt, diagrams
tests/            rules, API, tour, playground, early access; run on SQLite and Postgres
render.yaml       Render Blueprint for both services
```

## Run locally

Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
python -m pytest                                        # add TEST_POSTGRES_URL=... to also test Postgres
```

Two terminals (mock payments, SQLite):

```bash
PAYWALL=off uvicorn vendors.app:app --port 8001
uvicorn app.main:create_app --factory --port 8000 --reload
```

Then open http://127.0.0.1:8000/docs, or run the whole demo in the terminal: `python -m app.demo --auto-approve`.

**Real USDC payments on the Solana test network:**
1. Run `python scripts/generate_secrets.py`.
2. Put its three values plus `RAIL=paykit` in `.env`.
3. Start the sellers without `PAYWALL=off`.

On startup the API tops up each agent wallet with its daily budget.

## Deploy

**1. Supabase (database)**
1. Create a project in region *Central EU (Frankfurt)*.
2. Click **Connect** and copy the **Session pooler** connection string.
3. Turn it into `DATABASE_URL`: replace `postgresql://` with `postgresql+psycopg://` and add `?sslmode=require`.

The API creates its tables on first start.

**2. Render (API and demo sellers)**
1. Push this repo to GitHub, then go to Render → **New → Blueprint** and pick the repo.
2. Run `python scripts/generate_secrets.py` locally.
3. In the API's environment, paste `OPERATOR_TOKEN`, `AGENT_KEYS`, `AGENT_WALLET_KEYS` and `DATABASE_URL`.
4. Set `VENDOR_BASE` to the sellers' public URL, then redeploy the API.
5. Check `https://<api>/health` and `https://<api>/docs`.

**3. Lovable (web app)**
1. Paste [`docs/LOVABLE_PROMPT.md`](docs/LOVABLE_PROMPT.md) into a new project.
2. Set the API URL, the GitHub URL and the diagram URL in `src/config.ts`.
3. Publish, then add the app's URL to `ALLOWED_ORIGINS` on Render.

## API

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/health` | anyone | Status, payment mode, whether a token is needed |
| GET | `/v1/catalog` | anyone | What agents can buy, agreed prices, agent rules |
| GET | `/v1/demo/steps` | anyone | The guided tour's steps in plain words |
| POST | `/v1/early-access` | anyone | Sign up for early access (rate-limited, spam trap) |
| GET | `/v1/early-access/count` | anyone | Number of sign-ups |
| POST | `/v1/agents/{agent_id}/call` | agent key | Buy something: 200 paid, 202 waiting, 403 blocked |
| GET | `/v1/state` | operator | Agents, purchases waiting for approval, recent purchases |
| POST | `/v1/approvals/{id}/approve`, `/deny` | operator | Decide a waiting purchase |
| POST | `/v1/agents/{agent_id}/freeze`, `/unfreeze` | operator | Kill switch |
| GET | `/v1/ledger.csv` | operator | Export for the accountant |
| POST | `/v1/demo/run?mode=tour\|auto` | operator | Start the guided tour or the automatic demo |
| POST | `/v1/demo/next`, `/v1/demo/stop` | operator | Run the next tour step, or end the tour |
| GET | `/v1/demo` | operator | Where the tour is and what it's waiting for |
| POST | `/v1/playground/buy` | operator | "Be the agent": try a purchase as a demo agent |
| GET | `/v1/early-access`, `/v1/early-access.csv` | operator | Sign-ups |
| DELETE | `/v1/early-access/{email}` | operator | Delete a sign-up on request |

"Operator" means the operator token, or no token when the server runs with `PUBLIC_DEMO=true` (for judging on the test network). Full schemas at `/docs`.

## Security

- **Two kinds of keys.** Agents spend only as themselves. The dashboard uses a separate operator token.
- **The browser never touches the database.** Tables live in a private schema that Supabase's public API doesn't expose, with row-level security on.
- **Secrets only in Render's environment.** Mainnet is switched off in this MVP.
- **Safe defaults in production.** The API refuses to start without keys, with an open CORS setting, or without Postgres.
- **Public endpoints are rate-limited.** The sign-up form has a spam trap and gives the same answer whether or not an email is already on the list.
- **`PUBLIC_DEMO=true`** lets judges approve and freeze without a token. Agents still need their keys. Turn it off after judging.

## Architecture details

![AgentBudget system architecture](docs/architecture-technical.svg)

The API keeps no state of its own; everything lives in Postgres. Budget decisions lock one agent's row while they check and reserve the money, so several API instances can never spend the same budget twice. The guided tour and the rate limiter keep their state in memory, so they assume one instance (fine on Render's free plan).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `dev` | `prod` turns on the safety checks |
| `DATABASE_URL` | SQLite file | Supabase session pooler URL in production |
| `ALLOWED_ORIGINS` | localhost | Comma-separated web app origins |
| `ALLOWED_ORIGIN_REGEX` | none | e.g. Lovable preview URLs |
| `OPERATOR_TOKEN` | none | Dashboard actions |
| `PUBLIC_DEMO` | `false` | Open dashboard actions for judges |
| `AGENT_KEYS` | none | `agent:key,agent:key` |
| `RAIL` | `mock` | `paykit` for real Solana payments |
| `NETWORK` | `localnet` | `localnet` (Solana test network) or `devnet` |
| `RPC_URL` | test network | Solana RPC |
| `AGENT_WALLET_KEYS` | none | `agent:base58secret,...` (test networks only) |
| `SANDBOX_AUTOFUND` | `true` | Top up wallets on the test network at startup and before each demo |
| `VENDOR_BASE` | `http://127.0.0.1:8001` | Where the demo sellers run |
| `CATALOG_PATH` | `app/catalog.json` | Items, prices, agent rules |
| `EXPLORER_TX_URL` | automatic | Receipt link template with `{tx}` |
| `DEMO_ENABLED` | `true` | The guided tour and demo |

## Honest limitations

- Runs on the Solana test network, not with real money.
- The server holds the agents' test keys. Next version: the customer owns the wallet and the limits are enforced on Solana.
- Seller data is made up. The CSV follows the DATEV layout loosely, not the official import format; the accounts are SKR03 examples to confirm with a tax advisor.
