# HAL

*Formerly AgentBudget. Some technical names (Render services, database schema) still use `agentbudget`.*

**Let AI agents buy what they need. Within your rules.**

HAL sits between an AI agent and the paid APIs it buys data from. It checks each purchase before it is paid, pays in USDC on Solana, and checks the data that comes back before the agent sees it:
- Small purchases go through on their own. Big ones wait for a person.
- Purchases from sellers or links that aren't on the approved list are blocked.
- A purchase that was already paid recently is answered from the stored result, for free. A runaway loop is stopped automatically.
- Hidden instructions in a seller's data are flagged or removed, and a trap link is traced back to the seller that sent it.
- One switch stops an agent. Every payment has a receipt on Solana that anyone can check.

### ▶ Try it live: **[https://solana-hal-payments.lovable.app/](https://solana-hal-payments.lovable.app/)**

Built for Superteam Germany's *Build an MVP with Solana at WHU* (2026). This repo is the **backend** (FastAPI on Render, Supabase Postgres).

![HAL: how a purchase flows](docs/architecture.svg)

*Both diagrams are animated on GitHub. For slides use the GIFs ([overview](docs/architecture.gif), [system](docs/architecture-technical.gif)) or the PNGs. The system view is under [Architecture details](#architecture-details).*

## For judges: 3 minutes

1. Open the live app: **[https://solana-hal-payments.lovable.app/](https://solana-hal-payments.lovable.app/)** (the first load can take about 30 seconds while the server wakes up). Opening the app also wakes the demo seller services.
2. Press **Take the 3-minute tour**. You're the person in charge. Press **Run step** to move on.
   - At step 2 HAL traces a hidden trap to the seller that sent it, and puts that seller under review.
   - At step 3 you approve a purchase. The request shows what the task already bought.
   - At step 5 a looping agent is paid for once, gets the stored result after that, and is stopped automatically. You switch it back on.
   - At step 7 you flip the kill switch by hand.
   - At step 8 you download the ledger: payments with their Solana receipt, and reused purchases at 0.00 with the payment they reused.
3. Then open **Be the agent** and try buying things yourself, including the suspicious link.

How we answer each point of the listing: [`docs/PRODUCT.md`](docs/PRODUCT.md).

## The problem in one paragraph

Agents can now pay for data per request: a company record for 5 cents, an exchange rate for 1 cent. Teams give their agent a wallet and hope. If the agent gets tricked by text it reads, gets stuck in a loop, or a seller raises the price, the wallet empties. The only alternative today is approving every purchase by hand. HAL sits between the agent and its money and applies the rules a person set.

## What it controls

Each purchase goes through the checks in this order. The first one that applies decides.

| # | Control | What happens | Where it is set |
|---|---|---|---|
| 1 | Kill switch | Stops one agent's spending, starting with its next purchase. | Switch per agent on the dashboard |
| 2 | Circuit breaker | More than 30 purchase attempts in one minute, or more than 20% of the daily budget spent in 10 minutes, stops the agent automatically, the same way as the kill switch. Refused attempts count too; checking again on a purchase that waits for approval does not. Only a person can switch the agent back on. | Fixed defaults in this version |
| 3 | Approved sellers and items | Only items on the list can be bought, and each agent only the items it was allowed. Any other link, including one from text the agent read, is refused before money moves. | Rules page |
| 4 | Purchase reuse | If the same agent already paid for the same purchase (same item, same details) and the result is still fresh, HAL sends the stored result and pays nothing. Reused purchases use no budget. Stored results are kept only for items with reuse, up to 256 KB, and deleted when the window ends. | Per item in `catalog.json`. Demo: exchange rate 1 hour, company record 7 days, news 15 minutes, credit report and live exchange rate never. |
| 5 | Repeat purchases | When a result can't be reused, the same purchase is paid at most twice per hour, across all tasks. A loop that starts a new task every time is still caught. | Fixed defaults in this version |
| 6 | Budgets | Per task and per day. Even many purchases at the same moment can't go over. | Rules page |
| 7 | Seller under review | Purchases from a seller under review wait for a person (see "Source of a trap"). | Automatic; ended by an operator |
| 8 | Your OK above a limit | Purchases above an agent's limit wait for a person. The request shows what the task already bought. Each approval works once, for one purchase. | Rules page |
| 9 | Agreed prices | Each item has an agreed price. If the seller asks for more, the payment isn't signed. | Rules page |

After a purchase is paid, HAL checks what came back:

| Control | What happens | Where it is set |
|---|---|---|
| Response firewall | Before the agent sees the data, HAL checks every text in it. Text that gives instructions to an AI agent (a fixed list of 20 patterns), asks for a payment, or contains a link that isn't on the approved list is listed in `content_flags`. For items set to `redact` (in the demo: news), texts with instructions or payment requests are replaced. The payment itself is already made at this point; the firewall protects what the agent does next. | Per item in `catalog.json` (`annotate` by default, `redact` for news) |
| Source of a trap | HAL remembers every link in a paid response. If an agent tries to buy one of those links within 24 hours and it is blocked, HAL names the seller and the purchase that sent it, and puts that seller under review. A stored result from that seller can still be reused, because no money moves. | Automatic. End a review with `POST /v1/sellers/restore`. `SELLER_REVIEW_AFTER` sets how many incidents start a review (default 1). |
| Receipts | Every payment is in the ledger with its Solana receipt. The CSV export also lists reused purchases at 0.00, with the payment whose result they reused. | — |

**What the Rules page changes:** for agents, the description, allowed items, task budget, daily budget and approval limit; for items, the name, description, seller name, address and agreed price. Changes are checked (a task budget can't exceed the daily budget, prices must be above zero, ...), apply to the very next purchase, and are written to a change history. Agents and items are archived, never deleted, so the ledger keeps its meaning.

**What it doesn't change yet:** the repeat and circuit-breaker limits (stored per agent in the database, with the defaults above), and each item's reuse window and firewall setting (loaded from `catalog.json` into the database on the first start and on **Reset demo**).

Every answer comes with a `reason_code` for software and a `reason` in plain words, e.g. *"This seller isn't on the approved list, so nothing was paid."* The tour's trap step adds where the link came from: *"The link came from News Wire (demo), purchase c5ac. News Wire (demo) is now under review: its next purchases wait for a person."*

## Using it with your own agent

1. **Add your agent** on the Rules page: what it may buy, its task and daily budgets, and above which amount it needs your OK. It gets its own key and wallet automatically (`GET /v1/agents/{agent_id}/key`).
2. **Add the sellers** your agent buys from: their address and the price you agreed to. Any service that takes payment per request on Solana works.
3. **Fill the wallet.** On the test network this happens automatically. With real money it would be USDC sent to the agent's wallet address.
4. **Change one line in your agent:** ask HAL instead of calling the seller directly (below).
5. **Watch the dashboard:** approve big purchases, flip the kill switch, download the ledger.

## Connect your agent

```python
import httpx

r = httpx.post(f"{API}/v1/agents/research-agent/call",
               headers={"Authorization": f"Bearer {AGENT_KEY}"},
               json={"task_id": "supplier-check-1", "tool": "company_lookup",
                     "params": {"name": "Duping Bahn GmbH"}})
```

| Answer | Meaning | What your agent does |
|---|---|---|
| `200` | Paid (`status: "settled"`) or answered from a stored result (`status: "reused"`, `amount: "0.00"`, `reused_from`) | Use `data`. The receipt is in `tx` (for a reused result, the receipt of the original payment). `content_flags` lists anything HAL found in the data, e.g. instructions aimed at agents. |
| `202` | Waiting for a person | Repeat the same request with `approval_id` every few seconds. |
| `403` | Blocked | Don't retry. `reason` says why. A blocked link that came from a paid response also has `caused_by`: the purchase whose data contained it. |

A complete example agent (Claude) is in [`examples/claude_agent.py`](examples/claude_agent.py).

## Repo layout

```
app/
  main.py         app setup: config checks, CORS, security headers, routers
  settings.py     every setting from environment variables; refuses to start if something is missing
  security.py     agent keys and the operator token
  policy.py       the rules: pure decision logic with reason codes and plain messages
  fingerprint.py  "the same purchase": the item plus its details, ignoring key order, spaces and case
  firewall.py     the response firewall: checks seller data before the agent sees it
  service.py      the purchase flow: lock, decide, reuse or reserve, pay, check the data, settle or release
  db.py           storage: Supabase Postgres (SQLite only for the automated tests)
  rails.py        Solana payments through Solana Pay Kit (plus a mock for tests)
  tour.py         the guided tour's steps, in plain words (one place for all tour text)
  demo.py         runs the tour (visitor-driven) or the full demo (automatic)
  ratelimit.py    limits for public endpoints
  sandbox.py      tops up agent wallets on the Solana test network
  rules.py        rules editing: validation, change history, demo reset
  catalog.json    the starting rules: fills an empty database, and Reset demo restores them
  api/            public.py, agent.py, operator.py
vendors/app.py    demo sellers: paid APIs behind a Solana paywall (its own service)
scripts/          generate_secrets.py (optional key overrides), fund_sandbox.py
examples/         claude_agent.py
supabase/         schema.sql (optional; the API creates its tables itself)
docs/             product brief (PRODUCT.md), pitch (PITCH.md), diagrams
tests/            policy, API, rules, settings, tour and playground; SQLite, and Postgres if TEST_POSTGRES_URL is set
.github/          CI: runs the tests on every push (SQLite and the mock payment rail)
render.yaml       Render Blueprint for the API and the two demo seller services
```

## Deploy and test on Render

Everything runs on Render. New work goes on a branch: point the services at that branch, test, merge into `main`, then point them back at `main`.

**1. Supabase (database)**
1. Create a project in region *Central EU (Frankfurt)*.
2. Click **Connect** and copy the **Session pooler** connection string.
3. Turn it into `DATABASE_URL`: replace `postgresql://` with `postgresql+psycopg://` and add `?sslmode=require`.

The API creates its tables on first start. Nothing else to set up.

**2. Render (API and demo sellers)**
1. Render → **New → Blueprint**, then pick the repo. It creates `agentbudget-api`, `agentbudget-vendors` and `agentbudget-newswire`, and generates `APP_SECRET` and `OPERATOR_TOKEN` by itself.
2. Open **agentbudget-api → Environment** and set:
   - `DATABASE_URL`
   - `VENDOR_BASE`: the vendors service's URL
   - `NEWS_VENDOR_BASE`: the News Wire service's URL (News Wire runs on its own service, so it counts as a separate seller)
   - `ALLOWED_ORIGINS`: the frontend's URL, `https://solana-hal-payments.lovable.app`
   - `ALLOWED_ORIGIN_REGEX`: value in [`.env.example`](.env.example)
3. Redeploy. Then check `https://<api>/health` and `https://<api>/docs`.

If something is missing, the API doesn't start, and its log lists every missing setting with the fix.

**3. Frontend**

The web app is live at **[https://solana-hal-payments.lovable.app/](https://solana-hal-payments.lovable.app/)** and talks only to this API.

**Branch testing notes**
- Switching a branch keeps the environment variables. Both branches use the same database, so don't run two branches at the same time against it.
- The automated tests run with `python -m pytest` (SQLite and a mock payment rail, no Render needed). Never point `TEST_POSTGRES_URL` at Supabase: the tests wipe their schema.

## API

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/v1/status` | anyone | Status, payment mode, whether a token is needed (used by the web app) |
| GET | `/health` | anyone | Same as `/v1/status`, for Render's health check (some ad blockers block this address) |
| GET | `/v1/catalog` | anyone | What agents can buy, agreed prices, agent rules |
| GET | `/v1/demo/steps` | anyone | The guided tour's steps in plain words |
| POST | `/v1/early-access` | anyone | Sign up for early access (rate-limited, spam trap) |
| GET | `/v1/early-access/count` | anyone | Number of sign-ups |
| POST | `/v1/agents/{agent_id}/call` | agent key | Buy something: 200 paid, 202 waiting, 403 blocked |
| GET | `/v1/state` | operator | Agents (with `saved_today`, `reused_today` and `frozen_reason`), purchases waiting for approval, recent purchases (with `caused_by`, `reused_from` and `content_flags`) |
| POST | `/v1/approvals/{id}/approve`, `/deny` | operator | Decide a waiting purchase |
| POST | `/v1/agents/{agent_id}/freeze`, `/unfreeze` | operator | Kill switch |
| GET | `/v1/ledger.csv` | operator | Export for the accountant: payments and reused purchases |
| POST | `/v1/demo/run?mode=tour\|auto` | operator | Start the guided tour or the automatic demo |
| POST | `/v1/demo/next`, `/v1/demo/stop` | operator | Run the next tour step, or end the tour |
| GET | `/v1/demo` | operator | Where the tour is and what it's waiting for |
| POST | `/v1/playground/buy` | operator | "Be the agent": try a purchase as a demo agent |
| POST | `/v1/demo/reset` | operator | Demo only: clear purchases, restore the starting rules, release kill switches, refill test wallets |
| GET | `/v1/rules` | operator | All agents and items, including archived ones |
| POST | `/v1/rules/agents`, `/v1/rules/items` | operator | Add an agent or an item |
| PATCH | `/v1/rules/agents/{agent_id}`, `/v1/rules/items/{tool}` | operator | Change rules, or archive with `{"active": false}` |
| GET | `/v1/rules/history` | operator | Who changed which rule, when, from what to what |
| GET | `/v1/sellers` | operator | Every seller with its status (`active` or `under_review`) and number of incidents |
| POST | `/v1/sellers/restore` | operator | End a review, with `{"origin": "<seller_origin>"}` in the body. Recorded in the change history. |
| POST | `/v1/sellers/{origin}/restore` | operator | The same, with the origin URL-encoded in the path. |
| GET | `/v1/early-access`, `/v1/early-access.csv` | operator | Sign-ups |
| GET | `/v1/agents/{agent_id}/key` | operator token only | An agent's key and wallet address, to connect a real agent |
| DELETE | `/v1/early-access/{email}` | operator | Delete a sign-up on request |

"Operator" means the operator token, or no token when `PUBLIC_DEMO=true` (for judging). Revealing agent keys always needs the real token. Full schemas at `/docs`.

## Security

- **Test networks only.** The code accepts only Solana's localnet sandbox or devnet. No setting can make it move real money.
- **Two kinds of keys.** Agents spend only as themselves, with keys derived from `APP_SECRET`. The dashboard uses a separate operator token.
- **Secrets only in Render's environment.** Render generates `APP_SECRET` and `OPERATOR_TOKEN`. Nothing secret is in the repo.
- **The browser never touches the database.** The tables live in their own schema, `agentbudget`, which Supabase's public Data API doesn't expose. Only the API reads them, through the connection string. If you create the tables with [`supabase/schema.sql`](supabase/schema.sql), row-level security is switched on as well; the tables the API creates by itself don't have it.
- **The API won't start half-configured.** A missing agent key or wallet, no operator token (unless `PUBLIC_DEMO=true`), a seller address that still points to this machine (with `RAIL=paykit`), or `*` in `ALLOWED_ORIGINS` stops it, with every problem listed in the log.
- **The sign-up form and the playground are rate-limited.** The sign-up form has a spam trap and gives the same answer whether or not an email is already on the list.
- **`PUBLIC_DEMO=true`** lets judges approve and freeze without a token. Agents still need their keys. Turn it off after judging.

## Architecture details

![HAL system architecture](docs/architecture-technical.svg)

The API keeps no state of its own; everything lives in Postgres. Budget decisions lock one agent's row while they check and reserve the money, so several API instances can never spend the same budget twice. The guided tour and the rate limiter keep their state in memory, so they assume one instance (fine on Render's free plan).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | local SQLite file (tests and local runs) | Supabase session pooler URL |
| `APP_SECRET` | none | One random string; each agent's key and test wallet are derived from it. Render generates it. |
| `OPERATOR_TOKEN` | none | Dashboard actions, and revealing agent keys. Render generates it. |
| `PUBLIC_DEMO` | `false` | Open dashboard actions for judges |
| `ALLOWED_ORIGINS` | localhost | Comma-separated web app addresses |
| `ALLOWED_ORIGIN_REGEX` | none | Lovable preview links: `https://([a-z0-9-]+\.)*(lovable\.app\|lovableproject\.com)` |
| `RAIL` | `mock` | `paykit` for real USDC payments on the test network |
| `NETWORK` | `localnet` | `localnet` (Solana sandbox) or `devnet` |
| `RPC_URL` | sandbox | Solana RPC |
| `VENDOR_BASE` | `http://127.0.0.1:8001` | The demo sellers' public URL |
| `NEWS_VENDOR_BASE` | same as `VENDOR_BASE` | News Wire's public URL. Its own service makes it a separate seller. |
| `SANDBOX_AUTOFUND` | `true` | Top up agent wallets to their daily budget on the localnet sandbox: at startup, before each demo and on Reset demo |
| `CATALOG_PATH` | `app/catalog.json` | The starting rules (the live rules are in the database) |
| `EXPLORER_TX_URL` | automatic | Receipt link template with `{tx}` |
| `DEMO_ENABLED` | `true` | The guided tour and demo |
| `SELLER_REVIEW_AFTER` | `1` | Incidents before a seller goes under review |
| `AGENT_KEYS`, `AGENT_WALLET_KEYS` | none | Optional overrides per agent (`scripts/generate_secrets.py`) |

## Honest limitations

This is an MVP. What it does not do yet:

- **Test networks only**, never real money. Seller data is made up.
- **The server holds the agents' test keys**, all derived from one secret (`APP_SECRET`). Fine on a test network, not for real money. Next version: the customer owns the wallet and the limits are enforced on Solana.
- **A slow loop isn't frozen.** A loop that stays under 30 attempts a minute and 20% of the daily budget per 10 minutes is only stopped by the daily budget. A runaway loop is stopped within seconds; a slow one is capped by the daily budget.
- **"The same purchase" is literal.** The item and its details must match, ignoring key order, extra spaces and upper/lower case. An extra detail (e.g. `"page": 1`) makes it a different purchase.
- **Busy agents can trip the breaker.** An agent that legitimately makes more than 30 purchases a minute is stopped. The limits can't be changed on the Rules page yet.
- **The firewall is a pattern list.** It catches the common phrasings of instructions and payment requests, not every possible one. Its findings are recorded, so the patterns can be improved. A flag for a link contains the link itself, so an agent that reads `content_flags` sees it.
- **The seller's asked price is only reported on the mock rail.** With Solana Pay Kit, an overpriced purchase is refused the same way, but the message can't name the price the seller asked.
- **One API instance.** The guided tour and the rate limiter keep their state in memory.
- **No delivery check yet.** HAL doesn't check that a seller's answer has the expected format.