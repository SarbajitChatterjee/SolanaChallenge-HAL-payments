# Rules page and demo reset (backend v0.4)

Only the additions below. Nothing else on existing pages changes.

## 1. Reset demo (Live demo page)
- Status line: secondary pill "Reset demo" (rotate-counter-clockwise icon) next to "Download ledger (CSV)".
- Small muted note under the buttons: "Reset demo is for demo purposes only."
- Confirm dialog: title "Reset the demo?", the given text, buttons "Reset demo" (red) and "Cancel".
- Confirm: `POST /v1/demo/reset`, close any open tour, toast the returned `message`, refetch state, catalog, rules, rules history.
- Tour start: a 409 from `/v1/demo/run` shows its `detail` in the tour's error state, with a "Reset demo" button that opens the same dialog.

## 2. New Rules page (/rules)
- Header nav: "Rules" between "Live demo" and "Connect your agent" (desktop and mobile). Added to the sitemap.
- Title "Rules" and the given subtitle.
- **Agents** (sky): one card per active agent with name, description, "Stopped" pill when frozen, "May buy:" chips (item names), Task budget / Daily budget / Needs your OK above in USDC. Buttons: Edit, Show key (only when a token is set), Archive. Archived agents under a collapsed "Archived agents" section with Restore.
- **Edit / Add agent**: side drawer on desktop, full-screen sheet on mobile. Fields with help text as specified; number fields step 0.01, min 0, "USDC" suffix; checkboxes for every active item (name, seller, price). Add also has "Name". Save sends only changed fields.
- **Show key** dialog: key with copy button, wallet address, and the password warning.
- **Archive / Restore**: confirm first (archive text as given), then update `active`.
- **Items** (yellow): table Name, Seller, Agreed price, Address, Status, Actions. `{vendor_base}...` addresses show "Demo seller"; others truncated with a tooltip. Archived rows muted with Restore. "Add item" / Edit form with the six fields and help text.
- **Change history** (slate): newest first; line one = time (de-DE 24h), "Operator" or "Demo visitor", plain action label, target; below, each field as "Daily budget: 25 → 30". Labels exactly as listed.
- **Errors**: 422 shows `detail` under the matching field and keeps the form open; anything else is a toast.
- No API set: page shows a banner pointing to Settings instead of silent sample data.

## Technical details
- `src/lib/api.ts`: new types `RuleAgent`, `RuleItem`, `RulesHistoryEntry`, `AgentKey`; methods `rules`, `rulesHistory(limit=100)`, `createAgent`, `updateAgent`, `createItem`, `updateItem`, `agentKey`, `demoReset`. `ApiError` gains optional `field` parsed from 422 bodies.
- `src/lib/queries.ts`: `useRules`, `useRulesHistory`; a shared `useRefreshAll()` that invalidates query prefixes `state`, `catalog`, `rules`, `rules-history`.
- New components: `src/components/rules/{AgentCard,AgentForm,ItemsTable,ItemForm,HistoryList,KeyDialog}.tsx`, `src/components/demo/ResetDemoDialog.tsx` (shared by demo page and tour error state).
- Drawer: shadcn Sheet (side right on desktop, full-screen on mobile via `useIsMobile`).
- New slate tone (border/tint/text tokens) added to `styles.css` and `Panel` tones.
- New route `src/routes/rules.tsx` with its own head() and `staticData: { sitemap: true }`.
- Changed-fields diff compares form values to the loaded record; amounts stay strings.
