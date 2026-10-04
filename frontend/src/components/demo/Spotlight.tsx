import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/** Dims the page and rings the element named by the step's focus. */
export function Spotlight({ focus, color }: { focus: string | null; color: string }) {
  const [rect, setRect] = useState<{
    top: number;
    left: number;
    width: number;
    height: number;
  } | null>(null);

  useEffect(() => {
    if (!focus) {
      setRect(null);
      return;
    }
    const element = document.querySelector(`[data-tour="${focus}"]`);
    if (!element) {
      setRect(null);
      return;
    }
    element.scrollIntoView({ behavior: "smooth", block: "center" });
    const update = () => {
      const box = element.getBoundingClientRect();
      setRect({ top: box.top, left: box.left, width: box.width, height: box.height });
    };
    update();
    const timer = window.setInterval(update, 250);
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [focus]);

  if (!rect || typeof document === "undefined") return null;

  const box = {
    top: rect.top - 10,
    left: rect.left - 10,
    width: rect.width + 20,
    height: rect.height + 20,
  };

  return createPortal(
    <div className="pointer-events-none fixed inset-0 z-40" aria-hidden="true">
      <div
        className="absolute rounded-3xl"
        style={{ ...box, boxShadow: "0 0 0 9999px rgba(42, 39, 71, 0.35)" }}
      />
      <div
        className="pulse-ring absolute rounded-3xl"
        style={{ ...box, ["--ring-color" as string]: color }}
      />
    </div>,
    document.body,
  );
}
