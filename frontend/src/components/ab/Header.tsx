import { Link, useRouterState } from "@tanstack/react-router";
import { Menu, Settings, X } from "lucide-react";
import { useState } from "react";

import logoAsset from "@/assets/hal-mark.png.asset.json";
import { useSettings } from "@/lib/settings";
import { cn } from "@/lib/utils";

const links = [
  { to: "/", label: "Home" },
  { to: "/demo", label: "Live demo" },
  { to: "/rules", label: "Rules" },
  { to: "/connect", label: "Connect your agent" },
  { to: "/early-access", label: "Early access" },
] as const;

const linkBase = "rounded-lg border-2 px-3 py-2 text-sm font-semibold transition-colors";
const linkIdle = "border-transparent bg-transparent hover:border-[var(--grid)] hover:bg-[var(--card)]";
const linkActive = "border-yellow-line bg-yellow-tint text-yellow-ink";
const mobileBase = "rounded-lg border-2 px-3 py-3 font-semibold transition-colors";

export function Header() {
  const { openSettings } = useSettings();
  const [open, setOpen] = useState(false);
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  const isActive = (to: string) => (to === "/" ? pathname === "/" : pathname.startsWith(to));

  return (
    <header className="sticky top-0 z-30 border-b-2 border-[var(--grid)] bg-background/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3">
        <Link to="/" className="flex items-center gap-2" onClick={() => setOpen(false)}>
          <img src={logoAsset.url} alt="" className="size-11 shrink-0 object-contain sm:size-12" />
          <span className="font-display text-xl font-bold">HAL</span>
        </Link>

        <nav className="ml-auto hidden items-center gap-1 md:flex" aria-label="Main">
          {links.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              activeOptions={{ exact: link.to === "/" }}
              className={cn(linkBase, isActive(link.to) ? linkActive : linkIdle)}
              aria-current={isActive(link.to) ? "page" : undefined}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <button
          type="button"
          onClick={() => openSettings()}
          className="panel-flat panel-white ml-auto grid size-10 place-items-center md:ml-2"
          aria-label="Settings"
        >
          <Settings className="size-4" aria-hidden="true" />
        </button>

        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="panel-flat panel-white grid size-10 place-items-center md:hidden"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
        >
          {open ? (
            <X className="size-4" aria-hidden="true" />
          ) : (
            <Menu className="size-4" aria-hidden="true" />
          )}
        </button>
      </div>

      <div
        className={cn("border-t-2 border-[var(--grid)] md:hidden", open ? "block" : "hidden")}
      >
        <nav className="mx-auto flex max-w-6xl flex-col px-4 py-2" aria-label="Main">
          {links.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              activeOptions={{ exact: link.to === "/" }}
              onClick={() => setOpen(false)}
              className={cn(mobileBase, isActive(link.to) ? linkActive : linkIdle)}
              aria-current={isActive(link.to) ? "page" : undefined}
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
