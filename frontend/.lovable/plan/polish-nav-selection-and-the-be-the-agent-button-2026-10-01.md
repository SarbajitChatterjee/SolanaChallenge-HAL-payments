# Polish nav selection and the Be the agent button

Two small visual fixes, no logic changes.

## 1. Nav bar selections (Header)

Current active nav link is only a pale background with yellow text — too subtle, and the hover state looks like a plain grey blob that doesn't fit the theme.

Change both desktop and mobile nav links to use the existing pill/panel system:

- Hover: `panel-flat panel-white` style (3px light border, white fill, rounded pill) so it matches the app's card look.
- Active: `panel-flat panel-yellow` look — yellow border `#FACC15`, yellow tint `#FFF9DB`, dark-amber text `#A16207`, rounded pill, same padding as now. The selected item clearly reads as a yellow AgentBudget pill.

Implementation: in `src/components/ab/Header.tsx`, apply a shared pill-ish className to `Link` elements plus `activeProps`/hover classes; reuse the token colors via `panel-flat panel-yellow` / `panel-flat panel-white` utilities already defined in `src/styles.css` (no new hardcoded colors).

## 2. "Open Be the agent" button (Connect page)

In `src/routes/connect.tsx` the final card's button says "Open Be the agent".

Change the label to just "Be the agent". Do not add "Open" outside the button — removing "Open" is the cleaner option per your message.

## Verification

- Check the build log shows no errors.
- Playwright check: hover and active states on the nav render as pills; /connect shows the button reading "Be the agent".
