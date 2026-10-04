# Approval outcome statuses in What happened

## Changes
- Recognize `approved` and `denied` event statuses in the shared status presentation.
- In the What happened table, render these outcomes as `Waiting for you → Approved` in amber/green or `Waiting for you → Denied` in amber/red, with the event reason underneath.
- Detect status changes for existing event rows between state polls and highlight the changed row for 1.5 seconds using its new outcome colour, while disabling animation for reduced-motion preferences.
- When Approve or Deny is clicked, keep both controls disabled for that approval, show the requested success toast only after the API succeeds, and immediately refresh state.
- Preserve all API endpoints, payloads, and other behavior.

## Verification
- Check type safety and the current build result.
- Exercise the Live demo table and approval controls in the browser where available, including the displayed labels and disabled state.
