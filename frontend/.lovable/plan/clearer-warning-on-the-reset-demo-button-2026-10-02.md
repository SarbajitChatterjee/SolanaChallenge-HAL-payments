# Clearer warning on the Reset demo button

Only the two copy/styling changes below. No API, logic, or layout changes.

## 1. Warning under the button group (Live demo)
Replace the plain muted note under the buttons (`src/routes/demo.tsx`, ~line 355, currently "Reset demo is for demo purposes only.") with a small professional warning line:

- A small warning icon (TriangleAlert) followed by the text:
  "Demo only. This demo runs on dummy data, dummy sellers and test wallets. Nothing here is a real purchase."
- Same place: right-aligned under the button group, `text-xs` muted styling so it stays subtle, matching the current design tokens (`text-ink-muted`).

## 2. Confirm dialog copy alignment
Update the description in `src/components/demo/ResetDemoDialog.tsx` so the dialog says the same thing in the same words: it runs on dummy data and dummy sellers, and resets purchases, approvals, rules, agent switches and test wallets while keeping sign-ups and history. Keep the existing title and buttons unchanged.

## Notes
- Both changes are frontend text/styling only; nothing touches the API or existing behavior.
- The same dialog is shared with the tour error state, so it inherits the new copy automatically.
