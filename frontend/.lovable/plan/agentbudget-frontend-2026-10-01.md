# AgentBudget — frontend

## About the router

This project is built on TanStack Router, and it cannot be swapped for React Router — that is fixed by the stack here. The practical effect is zero: you get the exact same four addresses (`/`, `/demo`, `/connect`, `/early-access`), the same `?tour=1` link, the same header and footer, the same behaviour. Only the internal link/page wiring differs. Everything else in your brief is followed as written.

No backend work: no database, no accounts, no server code. The browser talks only to your FastAPI service.

## Settings and links

- API address defaults to `https://agentbudget-api.onrender.com`, changeable in the gear dialog, remembered in the browser along with the operator token. "Test connection" checks `/health` and says "Connected" or the problem in plain words.
- GitHub link: `https://github.com/SarbajitChatterjee/SolanaChallenge-HAL-payments`.
- Overview diagram: `https://raw.githubusercontent.com/SarbajitChatterjee/SolanaChallenge-HAL-payments/main/docs/architecture.svg`. If that file isn't in the repo yet, the diagram box will show a plain fallback — tell me the real path and I'll change the one line.

## Pages

**Home** — hero, the problem ("Today you can..." three cards), who it's for, how it works with the diagram and four numbered steps, why Solana with the two-slider cost calculator and the live comparison sentence, six control cards, early-access band with the sign-up count when it reaches 10.

**Live demo** — status line (mock / test network / devnet) with tour and CSV buttons; agent bands with task and daily meters, wallet, approval limit and the kill switch; "Waiting for you" approvals with Approve/Deny; two tabs: the statement table (time, agent, purchase, amount, outcome label with colour and icon, reason, receipt link, filters, new-row highlight) and "Be the agent" playground (pick agent, pick item or the suspicious 25 USDC link, ask to buy, result card with inline approve, raw JSON panel, per-visitor task id).

**Guided tour** — intro modal, then a floating card (bottom sheet on mobile) driven by `/v1/demo/steps` and polled `/v1/demo`: run-step, running spinner, "Your turn" for the approval and both kill-switch flips, "Finish the tour", eight-check summary, error state with "Start again". A dimming spotlight scrolls to and rings the element named by each step's `focus`, while still letting you click it. Esc and × end the tour.

**Connect your agent** — three numbered steps, Python / JavaScript / curl tabs with copy buttons using your real API address and first catalog item, the three-answer table, the full reason-code table, a live catalog table, and the link back to the playground.

**Early access** — email, role radio, optional use case, required consent, hidden spam field; success message replaces the form; field-level 422 messages; the 429 wait message.

## Behaviour

- `/demo` polls state every 1.5 s, pauses when the tab is hidden, keeps the last data while refreshing.
- `/health` on start; if the server demands a token and none is set, Settings opens with that explanation. Any 401 opens Settings too.
- Already-decided approvals show "Someone already decided this one." then refresh.
- Unreachable API: last data stays, with a slim banner naming the address and the ~30 second wake-up note, plus Retry.
- No API configured: the demo shows built-in sample data with a visible "Sample data" banner.

## Look

Light `#FBFAFF` with a faint dot grid; chunky 3 px coloured card borders with matching tint and a hard offset shadow; the colour-per-meaning palette exactly as you listed; Fredoka headings, Nunito Sans body, tabular numbers; pill buttons; the 44×64 kill-switch housing with a sliding lever as the signature control. Motion stays short, and stops under reduced-motion. Works down to 360 px: bands stack, tables scroll, the tour card becomes a bottom sheet. No dark mode, no glass, no gradients beyond one small Solana accent.

## Technical notes

- All requests live in `src/lib/api.ts` (typed per the contract, decimal strings kept as strings for display); `src/config.ts` holds the constants; `src/lib/sample.ts` holds the typed `/v1/state` fixture.
- TanStack Query for fetching and polling; `sessionStorage` for the playground task id; `localStorage` keys `agentbudget.apiBaseUrl` and `agentbudget.operatorToken`.
- CSV pulled as a blob with the auth header and saved as `agentbudget-ledger.csv`.
- shadcn/ui primitives (dialog, tabs, slider, radio, switch, table) restyled to the palette; lucide icons; sonner for toasts.
- Fonts loaded via a `<link>` in the root document head.
