import { useEffect, useRef } from "react";

import { useHealth } from "@/lib/queries";
import { useSettings } from "@/lib/settings";

/** On app start: check /health and ask for a token if the server needs one. */
export function AppBoot() {
  const { operatorToken, openSettings } = useSettings();
  const health = useHealth();
  const asked = useRef(false);

  useEffect(() => {
    if (asked.current) return;
    if (health.data?.auth_required && !operatorToken) {
      asked.current = true;
      openSettings("This server needs an operator token to show the live demo.");
    }
  }, [health.data, operatorToken, openSettings]);

  return null;
}
