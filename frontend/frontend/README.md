# Agent Budget Pro

Build the web app for **AgentBudget**. AgentBudget lets AI agents buy data on their own, within rules a person sets. Visitors must understand it in one minute and try it in three.

The backend already exists (FastAPI on Render). You build the **frontend only**.

---

## 1. Hard rules

- **Frontend only.** Do not connect Supabase. Do not create tables, edge functions, auth or any server code. No database access from the browser.
- All network calls go through **one typed module, `src/lib/api.ts`**. No other file calls `fetch`.
- Never hard-code tokens. The operator token is typed in by the user (Settings) and kept in `localStorage`.
- Stack: React + Vite + TypeScript + Tailwind, TanStack Query, React Router, shadcn/ui where useful, lucide icons.
- **Show backend text as-is.** Tour steps, purchase reasons and agent descriptions come from the API in plain words. Do not rewrite or summarise them.
- **Copy rules for everything you write yourself:** short sentences, plain words, talk to the reader as "you". Say "USDC", "approved list", "budget", "receipt". Never use: seamless, leverage, robust, empower, unlock, revolutionize, cutting-edge, next-gen, game-changing, synergy, agentic, Web3, "in today's world". No emoji.

## 2. Configuration

`src/config.ts`:
```ts
export const DEFAULT_API_BASE_URL = "https://agentbudget-api.onrender.com";     // I will replace this
export const ARCHITECTURE_IMAGE_URL =
  "https://raw.githubusercontent.com/<user>/<repo>/main/docs/architecture.svg";  // animated overview
export const GITHUB_URL = "https://github.com/<user>/<repo>";
export const POLL_MS = 1500;
```
A **Settings** dialog (gear icon in the header) lets the user change the API base URL and enter an operator token. Store them as `agentbudget.apiBaseUrl` and `agentbudget.operatorToken` in `localStorage`. Add a "Test connection" button that calls `GET /health` and shows "Connected" or the error in plain words.

## 3. Pages and navigation

Header: wordmark "AgentBudget", nav links **Home**, **Live demo**, **Connect your agent**, **Early access**, gear icon. On mobile, the nav collapses into a menu.
Footer: "Built for Superteam Germany's Solana challenge at WHU, 2026." Links: GitHub, API docs (`<apiBaseUrl>/docs`), API version from `/health`.

### 3.1 Home (`/`)

Purpose: a judge or visitor understands the problem, who it's for, how it works and why Solana, without scrolling forever. Sections, in order:

1. **Hero**
   - Title: "Let AI agents buy what they need. Within your rules."
   - Text: "AgentBudget is a spending account for AI agents. Small purchases go through on their own. Big ones wait for you. Wrong ones are blocked. One switch stops everything."
   - Buttons: "Take the 3-minute tour" (→ `/demo?tour=1`, primary) and "Get early access" (→ `/early-access`).

2. **The problem.** Heading: "Agents can pay now. Nobody can safely let them."
   - Lead text: "An agent that checks a new supplier needs a company record, an exchange rate, recent news and maybe a credit report. Each costs between 1 and 50 cents, from a different seller."
   - Three cards titled "Today you can...":
     - "Give it a credit card." Body: "Cards can't handle 5-cent payments, and nothing stops the agent from spending more."
     - "Give it a wallet with money." Body: "It can pay anyone, instantly. If it gets tricked or stuck in a loop, the wallet empties."
     - "Approve every purchase by hand." Body: "Safe, but then it's not an agent anymore."

3. **Who it's for.** Heading: "Built first for teams whose agents already pay per request." Two cards:
   - "You build the agent": "Your agent buys data per request and holds its own wallet. You want limits without writing them yourself." Link "Connect your agent" → `/connect`.
   - "You approve the spending": "You want small purchases to just happen, the big ones to come to you, and a record your accountant can use." Link "Try the live demo" → `/demo?tour=1`.

4. **How it works.** Heading: "One question before every purchase."
   - Show `ARCHITECTURE_IMAGE_URL` as an `<img>` (alt "How a purchase flows through AgentBudget"), full width, rounded, lazy-loaded.
   - Four numbered steps under it: "The agent asks to buy." / "AgentBudget checks your rules." / "It pays the seller in USDC on Solana." / "The receipt goes into your ledger."

5. **Why Solana**, with an **interactive cost calculator**.
   - Heading: "Why this only works on Solana."
   - Three short points: "Payments of a few cents cost a fraction of a cent." / "Sellers don't need an account for your agent: it just pays." / "The agent's wallet only holds its budget, so it can't spend more, even if software fails."
   - Calculator, two sliders:
     - "Purchases per month": 100 to 100,000, logarithmic, default 1,000.
     - "Average price": 1 to 50 cents, default 2.
   - Two horizontal bars with numbers:
     - "Typical online card fees (2.9% + 0.30 USD each)": `n × (0.30 + 0.029 × price)`.
     - "Solana network fees (about 0.0013 USD each)": `n × 0.0013`.
   - Also show "Value of what the agent bought: n × price".
   - A sentence that updates live, e.g. "Card fees would be 15× the value of the data. On Solana they're 1.30 USD."
   - Small print: "Card example uses typical online card pricing. Solana figure is the median network fee reported by Solana Pay Kit. Your numbers will vary."

6. **What you control.** Six small cards with an icon each:
   - "Approved sellers": "Only sellers on your list can be paid."
   - "Agreed prices": "If a seller asks for more, nothing is paid."
   - "Budgets": "Per task and per day."
   - "Your OK above a limit": "Big purchases wait for you."
   - "Kill switch": "Stops one agent instantly."
   - "Receipts": "Every payment has a Solana receipt and goes into an export for your accountant."

7. **Early access band.**
   - Heading: "We're looking for our first 10 teams."
   - Text: "Free setup, and we connect your agent with you in a 30-minute call."
   - Button: "Get early access".
   - If `GET /v1/early-access/count` returns 10 or more, add "{count} teams have signed up."

### 3.2 Live demo (`/demo`): dashboard + guided tour + playground

Layout, top to bottom:

- **Status line.** Rail text: mock → "Mock mode: no real payments"; paykit + localnet → "Paying in USDC on the Solana test network"; paykit + devnet → "Paying in USDC on Solana devnet". Buttons on the right: "Start the guided tour" and "Download ledger (CSV)".

- **Agents** (`data-tour="agents"`). One band per agent:
  - name, `description`, and "May buy: {item names}" (map tool ids to names from `/v1/catalog`).
  - "This task": `current_task.spent` of `per_task_cap`, with a thin meter that turns red at 99 % or more. If there is no task yet: "No task yet".
  - "Today": `spent_today` of `daily_cap`, with a meter.
  - "Wallet": `wallet_usdc` + " USDC" with the truncated address and a copy button, or "–" in mock mode. Under it: "Needs your OK above {approval_above} USDC".
  - **Kill switch** (`data-tour="breaker"` on the research-agent switch): see Design. When running: label "Running", sub-label "Flip to stop spending". When frozen: label "Stopped", sub-label "Flip to let it buy again". Clicking calls freeze or unfreeze. A frozen band gets a soft diagonal hatch.

- **Waiting for you** (`data-tour="approvals"`, only when there are pending approvals). One row per approval:
  - Text: "**{agent_id}** wants **{item_name}** from {vendor} for **{amount} USDC**". Under it, `reason`.
  - Buttons "Approve" and "Deny". Use `aria-live="assertive"`.

- **Two tabs:** "What happened" (the statement, default) and "Be the agent" (the playground).

**Statement** (`data-tour="statement"`, ledger-style table, newest first):
- Columns: Time (de-DE, 24 h), Agent, Purchase (`item_name` or the URL, with the vendor muted underneath), Amount (USDC, right-aligned), What happened, Receipt.
- "What happened": a label from `status` with colour and icon. settled = "Paid" (green). held = "Waiting for you" (amber). blocked = "Blocked" (red). failed = "Didn't go through" (red). reserved = "Paying…" (grey). control = "Kill switch" (dark).
- Always show `reason` under the label.
- Receipt: if `explorer_url`, a link "View receipt" (new tab); else if `tx` starts with "mock-", "Test receipt"; else "–".
- Rows that are new since the last poll get a short highlight. Blocked rows get a red left border.
- Filters: agent, and All / Paid / Waiting / Blocked.
- Empty state: "Nothing yet. Start the guided tour, or try a purchase in Be the agent."
- `data-tour="ledger"` on the Download ledger button.

**Be the agent** (playground):
- Intro: "You're the agent now. Pick what to buy and see what AgentBudget does."
- Step 1: "Which agent are you?" Two cards from `/v1/catalog.agents`, with description and rules.
- Step 2: "What do you want to buy?"
  - One card per catalog item: name, description, seller, "{price} USDC".
  - A card styled as a warning: "A link from a news result", "A 25 USDC 'full dossier' from a seller you've never seen." This sends `url: "https://dossier-deals.example/full-dossier"`.
- Button "Ask to buy". It calls `POST /v1/playground/buy` with `{agent_id, tool | url, task_id}`.
  - `task_id` is `"playground-" + 6 random chars`, stored in `sessionStorage`, so each visitor has their own task budget.
  - Show "Your task budget: {spent} of {cap}" for the chosen agent, plus a "Start a new task" button that makes a new id.
- Result card, animated in:
  - 200: green, "Paid", `reason`, receipt link.
  - 202: amber, "Waiting for you", `reason`, with inline "Approve" / "Deny". Approve calls approve, then repeats the buy with the same body plus `approval_id`, and shows the new result.
  - 403/502: red, "Blocked" or "Didn't go through", with `reason`.
- Below the result, a collapsible "What your agent's code receives" showing the raw JSON.

#### The guided tour (most important feature)

Start it with "Start the guided tour", or automatically when the URL has `?tour=1`.

0. **Intro modal** (frontend only):
   - Title: "You're in charge for 3 minutes."
   - Text: "An AI agent is about to check a new supplier and buy the data it needs. You'll watch each purchase and see what AgentBudget does. Twice, you'll have to act."
   - Buttons: "Start" (calls `POST /v1/demo/run?mode=tour`) and "Not now".

1. **Tour card**: a floating panel, bottom-right on desktop, bottom sheet on mobile.
   - Progress: "Step {i} of {total}", plus a dotted progress bar.
   - Steps come from `GET /v1/demo/steps` (title, what_happens, why_it_matters, focus, your_turn). Poll `GET /v1/demo` every `POLL_MS` while the tour is open.

   States:
   - `waiting_for == "next"` at step k:
     - If k > 1, show a "Done: {title of step k-1}" block with its `why_it_matters` and a green check.
     - Then show "Up next: {title of step k}" with its `what_happens`.
     - Primary button "Run step {k}", which calls `POST /v1/demo/next`.
   - Running (`waiting_for == null` and `running`): show step k's title and `what_happens`, plus a small spinner "Watching the agent…".
   - `waiting_for == "approval"`:
     - Big amber callout "Your turn" + `your_turn`.
     - Spotlight the approvals box (see below).
     - The card waits; the tour continues on its own once you decide.
   - `waiting_for == "kill_switch_on"`: callout "Your turn: flip the yellow switch next to research-agent." Spotlight the switch.
   - `waiting_for == "kill_switch_off"`: callout "It was refused. Now flip the switch back." Spotlight the switch.
   - Step "ledger" waiting for next: show its text and `your_turn`. The button reads "Finish the tour".
   - `finished`: a summary card "That's AgentBudget." with eight green checks, one per step title. Buttons: "Try it yourself" (switches to Be the agent), "Get early access", "Download the ledger".
   - `error`: show it in plain words with "Start again".

2. **Spotlight**:
   - For each step, find the element with `data-tour == step.focus`, scroll it into view, dim the rest of the page with a soft overlay (35 % opacity) and outline the element with a pulsing ring in the step's colour.
   - Clicks must still reach the spotlighted element (approve buttons, switch).
   - The pulse stops when `prefers-reduced-motion` is set.

3. "End tour" (×) calls `POST /v1/demo/stop`. Esc closes the card. Keyboard focus moves into the card on open.

### 3.3 Connect your agent (`/connect`)

For developers. Title: "Connect your agent in three steps." Numbered cards:

1. **"Get a key for your agent."** "Whoever runs AgentBudget gives each agent its own key. The key can only spend as that agent, within that agent's rules."
2. **"Ask before you buy."** Code tabs Python / JavaScript / curl. Use the real API base URL and the first catalog item.
   - Python example:
     ```python
     r = httpx.post(f"{API}/v1/agents/research-agent/call",
                    headers={"Authorization": f"Bearer {AGENT_KEY}"},
                    json={"task_id": "supplier-check-1", "tool": "company_lookup",
                          "params": {"name": "Beispiel GmbH"}})
     ```
   - A copy button on every code block.
3. **"Handle three answers."** A three-row table:
   - 200 Paid: "The data is in `data`. The receipt is in `tx`."
   - 202 Waiting for a person: "Repeat the same request with `approval_id` every few seconds until it's 200 or 403."
   - 403 Blocked: "Don't retry. `reason` says why in plain words; `reason_code` is for your code."

Then:
- **"Every reason, explained."** A table of `reason_code` → meaning:
  - paid: "Paid"
  - needs_approval: "Above your approval limit"
  - approval_pending: "Still waiting for a person"
  - approval_denied: "A person said no"
  - approval_used: "That approval was already used"
  - not_in_catalog: "Seller isn't on the approved list"
  - not_allowed: "This agent may not buy this"
  - task_budget: "Task budget would be exceeded"
  - daily_budget: "Daily budget would be exceeded"
  - price_too_high: "Seller asked more than the agreed price"
  - frozen: "Agent is stopped by the kill switch"
  - payment_failed: "Payment didn't go through, safe to retry later"
- **"What agents can buy."** A live table from `/v1/catalog`: name, seller, agreed price.
- A final card: "Rather click than code? Try the same purchases in Be the agent." → `/demo` with the playground tab open.

### 3.4 Early access (`/early-access`)

- Title: "Get early access."
- Text: "We're onboarding 10 teams first. Free setup, and we'll connect your agent with you."
- Form fields:
  - Email (required).
  - "Which fits you best?" Radio:
    - builder = "I build AI agents"
    - approver = "I approve software spending"
    - vendor = "I sell an API that agents pay for"
    - curious = "Just curious"
  - "What should your agent be able to buy?" Optional, up to 500 characters.
  - Consent checkbox (required): "You may email me about AgentBudget early access. I can ask you to delete my email at any time."
  - A hidden honeypot input named `website`: visually hidden, `tabIndex=-1`, `autoComplete="off"`.
- Submit → `POST /v1/early-access`.
  - On success, replace the form with "Thanks! We'll get in touch within a few days."
  - 422 errors: show the server message next to the field.
  - 429: "Too many tries. Please wait a minute."

## 4. API contract (exact; samples are real responses)

Base: `apiBaseUrl`. Send `Authorization: Bearer <operatorToken>` on operator endpoints when a token is set. Amounts are decimal strings (format with 2 decimals, never float math for display). Timestamps are ISO UTC. Errors return `{ "detail": string }`.

```ts
// public
GET  /health -> { ok, version, rail: "mock"|"paykit", network: string|null, database, auth_required: boolean, demo_enabled: boolean }
GET  /v1/catalog -> { items: {tool,name,description,vendor,price}[], agents: {agent_id,description,allowed_tools,per_task_cap,daily_cap,approval_above}[] }
GET  /v1/demo/steps -> { index, key, title, what_happens, why_it_matters, focus: "agents"|"statement"|"approvals"|"breaker"|"ledger", your_turn: string|null }[]
POST /v1/early-access { email, role: "builder"|"approver"|"vendor"|"curious", use_case?: string, consent: true, website?: "" } -> { ok, message }
GET  /v1/early-access/count -> { count }

// operator (token, or open when the server runs PUBLIC_DEMO)
GET  /v1/state -> State
POST /v1/approvals/{id}/approve | /deny       (409 = already decided)
POST /v1/agents/{agent_id}/freeze | /unfreeze
GET  /v1/ledger.csv                           (fetch as blob with auth header, save as agentbudget-ledger.csv)
POST /v1/demo/run?mode=tour -> Demo           (started=false if one is already running: then just attach to it)
POST /v1/demo/next -> Demo                    (409 if not waiting for next)
POST /v1/demo/stop -> Demo
GET  /v1/demo -> Demo
POST /v1/playground/buy { agent_id, tool?, url?, task_id, approval_id? } -> Purchase (200 | 202 | 403 | 502)

type Demo = { running: boolean; finished: boolean; mode: "tour"|"auto"; started?: boolean|null;
  step_key: string|null; step_index: number; step_total: number;
  waiting_for: "next"|"approval"|"kill_switch_on"|"kill_switch_off"|null;
  approval_id: string|null; task_id: string|null; error: string|null; log: string[] };

type Purchase = { decision: "allow"|"hold"|"deny"; status: string; reason_code: string; reason: string;
  amount?: string; vendor?: string; item_name?: string; tx?: string|null; explorer_url?: string|null;
  approval_id?: string; data?: unknown };
```

Real samples:

```json
// 200 paid
{"decision":"allow","status":"settled","reason_code":"paid","reason":"Paid 0.05 USD to Registry Data (demo).","amount":"0.05","vendor":"Registry Data (demo)","tool":"company_lookup","item_name":"Company record","tx":"mock-02a1bbadc4e74189","explorer_url":null}
// 403 blocked
{"decision":"deny","status":"blocked","reason_code":"not_in_catalog","reason":"This seller isn't on the approved list, so nothing was paid."}
// 202 waiting
{"decision":"hold","status":"pending","reason_code":"needs_approval","reason":"0.50 USD is above the 0.25 USD limit for automatic purchases, so a person has to approve it.","approval_id":"c8a44374fa68","amount":"0.50","item_name":"Credit report"}
// GET /v1/demo right after starting the tour
{"running":true,"finished":false,"mode":"tour","started":null,"step_key":"everyday","step_index":1,"step_total":8,"waiting_for":"next","approval_id":null,"task_id":"supplier-check-9207","error":null,"log":[]}
// one tour step
{"index":3,"key":"approval","title":"A bigger purchase","what_happens":"The agent wants a credit report for 0.50 USDC. Purchases above 0.25 USDC need a person's OK.","why_it_matters":"Anything above your limit waits for you. The agent can't skip this step.","focus":"approvals","your_turn":"Approve or deny the credit report in “Waiting for you”."}
```

`GET /v1/state` sample (also use it as typed fixture data in `src/lib/sample.ts`):
```json
{"rail":"mock","network":null,
 "agents":[
  {"agent_id":"research-agent","description":"Checks new suppliers before a first order.","frozen":false,"allowed_tools":["company_lookup","credit_report","fx_rate","fx_realtime","news_search"],"per_task_cap":"0.75","daily_cap":"25.00","approval_above":"0.25","spent_today":"0.05","current_task":{"task_id":"playground-7f3a","spent":"0.05"},"wallet_address":null,"wallet_usdc":null},
  {"agent_id":"intern-agent","description":"Looks up exchange rates and news. Nothing else.","frozen":false,"allowed_tools":["fx_rate","news_search"],"per_task_cap":"0.20","daily_cap":"2.00","approval_above":"0.05","spent_today":"0.00","current_task":null,"wallet_address":null,"wallet_usdc":null}],
 "approvals":[
  {"id":"c8a44374fa68","created_at":"2026-10-01T09:42:01.232632+00:00","agent_id":"research-agent","task_id":"playground-7f3a","tool":"credit_report","item_name":"Credit report","vendor":"Credit Bureau (demo)","amount":"0.50","reason":"0.50 USD is above the 0.25 USD limit for automatic purchases, so a person has to approve it.","status":"pending"}],
 "events":[
  {"id":"745f2d01c781","created_at":"2026-10-01T09:42:01.233548+00:00","agent_id":"research-agent","task_id":"playground-7f3a","tool":"credit_report","item_name":"Credit report","url":"http://127.0.0.1:8001/v1/credit-report","vendor":"Credit Bureau (demo)","amount":"0.50","decision":"hold","status":"held","reason_code":"needs_approval","reason":"0.50 USD is above the 0.25 USD limit for automatic purchases, so a person has to approve it.","tx":null,"explorer_url":null},
  {"id":"636f195b78fc","created_at":"2026-10-01T09:42:01.228213+00:00","agent_id":"research-agent","task_id":"playground-7f3a","tool":null,"item_name":null,"url":"https://dossier-deals.example/full-dossier","vendor":null,"amount":null,"decision":"deny","status":"blocked","reason_code":"not_in_catalog","reason":"This seller isn't on the approved list, so nothing was paid.","tx":null,"explorer_url":null},
  {"id":"d20ca0de35ba","created_at":"2026-10-01T09:42:01.218935+00:00","agent_id":"research-agent","task_id":"playground-7f3a","tool":"company_lookup","item_name":"Company record","url":"http://127.0.0.1:8001/v1/company","vendor":"Registry Data (demo)","amount":"0.05","decision":"allow","status":"settled","reason_code":"paid","reason":"Paid 0.05 USD to Registry Data (demo).","tx":"mock-02a1bbadc4e74189","explorer_url":null}]}
```

## 5. Data behaviour

- Poll `GET /v1/state` every `POLL_MS` on `/demo`. Pause when the tab is hidden. Keep previous data while refetching.
- On app start, call `GET /health`. If `auth_required` is true and no token is set, open Settings with: "This server needs an operator token to show the live demo."
- Any 401: open Settings with "The operator token is missing or wrong."
- 409 on approve/deny: toast "Someone already decided this one." Then refresh.
- Network failure: keep the last data, show a slim banner: "Can't reach the API at {url}. Free servers take about 30 seconds to wake up." Add a Retry button.
- If no API URL is configured, `/demo` shows `sample.ts` with the banner "Sample data. Connect the API in Settings to try it live." Never show sample data silently.

## 6. Design

Match the animated overview diagram: friendly, light, slightly cartoonish, 2D.

- Background `#FBFAFF` with a faint dot grid (`#E4E0F7`, 28 px).
- Cards: a 3 px border in the card's colour, a soft tint of the same colour inside, rounded 20–28 px, and a faint tinted shadow offset 6 px (the border colour at 25 % opacity, no blur).
- Colour per meaning (border / tint / text):
  - agents: sky `#38BDF8` / `#E8F7FE` / `#0369A1`
  - dashboard and approvals: pink `#F472B6` / `#FDEEF6` / `#BE185D`
  - AgentBudget itself: yellow `#FACC15` / `#FFF9DB` / `#A16207`
  - ledger: mint `#34D399` / `#E7FAF2` / `#047857`
  - Solana: purple `#A78BFA` / `#F3EEFF` / `#6D28D9`
  - paid: green `#4ADE80` / `#EAFBF0` / `#15803D`
  - blocked: red `#F87171` / `#FEF0F0` / `#B91C1C`
  - waiting: amber `#FBBF24` / `#FFF8E1` / `#B45309`
- Type:
  - Headings: "Fredoka" 600/700 (Google Fonts). Body: "Nunito Sans" 400/600, 16 px.
  - Tabular numbers for all amounts.
  - Text colour `#2A2747`, muted `#6B6890`.
- **Kill switch** is the signature element: a 44×64 px housing with yellow border and tint, and a dark-amber lever. The lever sits up when running and down when stopped, with a 150 ms slide.
- Buttons: pill-shaped. Primary = yellow border, yellow tint, dark-amber text. Destructive = red border and tint.
- Motion:
  - Short and purposeful: new rows highlight, result cards slide in 8 px, the spotlight ring pulses.
  - Respect `prefers-reduced-motion`.
- Avoid: dark mode, glassmorphism, big gradients (only Solana's purple-to-green may appear as a small accent), ALL-CAPS labels, eyebrow labels above headings, arrows appended to button text, stock photos.
- Accessible:
  - Visible focus rings.
  - Colour never the only signal (always a word and an icon).
  - Labels on every input. Spotlight and modal trap focus correctly.
- Responsive down to 360 px. Agent bands stack, the tour card becomes a bottom sheet, tables scroll inside their own container.

## 7. Done when

- With no API configured, `/demo` renders the sample data, and Home, Connect and Early access render fully.
- With the API configured:
  - The guided tour runs all 8 steps. I approve the credit report and flip the switch twice when asked. The summary appears at the end.
  - In "Be the agent" I can buy, get blocked by the suspicious link, and approve a credit report inline.
  - The early access form stores a sign-up and shows the thank-you message.
  - The CSV downloads.

---

SHould you have questions, claify them with me whenever you get them

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/f6fc06c7-bc77-4000-8b5a-a8360df18118).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
