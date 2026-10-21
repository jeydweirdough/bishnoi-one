"use client";

import { Check, CircleAlert, LayoutGrid, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { APP_TILES } from "../lib/app-tiles";
import { addressKnown, appLabel, appUrl, THIS_APP, type AppName } from "../lib/apps";

// The app launcher (decided 2026-10-21, after Zoho's): a grid button in the
// top bar of every app, opening a panel of the Bishnoi One apps as tiles.
// A tile goes through the Platform's /go, which hands the app a pass, so the
// person arrives signed in; the Platform also says no, in words, to an app
// their company doesn't have or they haven't been given: that answer comes
// back to the page the panel was opened on (&from=, ?appNotice=) as an alert
// over it, so nobody is left on the Platform's page. The tiles
// (icons, colours) are in lib/app-tiles.ts, shared with the sign-in page.
//
// Same file in every app's src/platform/shell/: copy it as it is.

/** Where a tile goes: through the Platform, so the app opens signed in; straight there when the Platform isn't known. */
function linkTo(app: AppName): string {
  if (app === "platform" || !addressKnown("platform")) return appUrl(app);
  return `${appUrl("platform")}/go?app=${app}&return=${encodeURIComponent(`${appUrl(app)}/auth/platform`)}`;
}

/** The same, saying which page to come back to if the Platform says no. */
function linkFromHere(app: AppName): string {
  const to = linkTo(app);
  return to.includes("/go?") ? `${to}&from=${encodeURIComponent(window.location.href)}` : to;
}

/** A refusal from the Platform, back on the page the launcher was opened on: shown over it, then taken out of the address. */
function useAppNotice(): [string | null, () => void] {
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    const url = new URL(window.location.href);
    const said = url.searchParams.get("appNotice");
    if (!said) return;
    setNotice(said.slice(0, 300));
    url.searchParams.delete("appNotice");
    window.history.replaceState(window.history.state, "", url.toString());
  }, []);
  useEffect(() => {
    if (!notice) return;
    const t = window.setTimeout(() => setNotice(null), 10_000);
    return () => window.clearTimeout(t);
  }, [notice]);
  return [notice, () => setNotice(null)];
}

export function AppLauncher() {
  const pathname = usePathname();
  // The panel belongs to the page it was opened on, so navigating closes it.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = openOn === pathname;
  const box = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const [notice, dismiss] = useAppNotice();

  // Its own small panel, not a kit popover, so this one file works in every app.
  useEffect(() => {
    if (!open) return;
    const outside = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpenOn(null);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpenOn(null);
      button.current?.focus();
    };
    document.addEventListener("mousedown", outside);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", outside);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  // Online, only the apps registered on the Platform; on this computer, all of them.
  const shown = APP_TILES.filter((t) => t.app === THIS_APP || addressKnown(t.app) || process.env.NODE_ENV !== "production");
  if (shown.length < 2) return notice ? <AppNotice text={notice} onClose={dismiss} /> : null;

  const panel = (
    <div className="w-[min(22rem,calc(100vw-2rem))] p-3">
      <p className="px-1 pb-2 text-meta font-semibold text-ink-3">Bishnoi One apps</p>
      <ul className="grid grid-cols-3 gap-1.5">
        {shown.map((t) => {
          const here = t.app === THIS_APP;
          const Icon = t.icon;
          const body = (
            <>
              <span className="relative grid size-12 place-items-center rounded-xl" style={{ background: t.tint, color: t.ink }}>
                <Icon className="size-6" aria-hidden />
                {here && (
                  <span className="absolute -right-1 -bottom-1 grid size-5 place-items-center rounded-full bg-ink text-white ring-2 ring-bench" aria-hidden>
                    <Check className="size-3" />
                  </span>
                )}
              </span>
              <span className="mt-1.5 text-sm font-semibold text-ink">{appLabel(t.app)}</span>
              <span className="text-[0.6875rem] leading-tight text-ink-3">{here ? "You're here" : t.blurb}</span>
            </>
          );
          return (
            <li key={t.app}>
              {here ? (
                <span aria-current="page" className="flex flex-col items-center rounded-xl bg-sheet px-1 py-2.5 text-center">
                  {body}
                </span>
              ) : (
                <a
                  href={linkTo(t.app)}
                  onClick={(e) => {
                    setOpenOn(null);
                    // A plain click carries this page along, for the Platform to come back to; a new tab opens as it is.
                    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
                    e.preventDefault();
                    window.location.href = linkFromHere(t.app);
                  }}
                  className="flex flex-col items-center rounded-xl px-1 py-2.5 text-center transition-colors hover:bg-sheet">
                  {body}
                </a>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );

  return (
    <div ref={box} className="relative">
      <button
        ref={button}
        type="button"
        aria-label="Bishnoi One apps"
        aria-expanded={open}
        aria-haspopup="true"
        title="Apps"
        onClick={() => setOpenOn(open ? null : pathname)}
        className={`grid size-10 place-items-center rounded-lg text-ink-2 transition-colors hover:bg-sheet hover:text-ink ${open ? "bg-sheet text-ink" : ""}`}
      >
        <LayoutGrid className="size-5" aria-hidden />
      </button>
      {open && <div className="absolute top-full right-0 z-50 mt-2 rounded-xl border border-rule bg-bench shadow-lg">{panel}</div>}
      {notice && <AppNotice text={notice} onClose={dismiss} />}
    </div>
  );
}

/**
 * "Your account doesn't include Inventory…": over the page, at the top, until
 * closed (or 10 seconds). Drawn on the page itself, not inside the top bar: the
 * top bar is there twice (the phone's, hidden on a wide screen, and the wide
 * one), and whichever of them reads the notice, it has to be seen.
 */
function AppNotice({ text, onClose }: { text: string; onClose: () => void }) {
  return createPortal(
    <div role="alert" className="fixed top-4 left-1/2 z-[60] flex w-[min(28rem,calc(100vw-2rem))] -translate-x-1/2 items-start gap-3 rounded-xl border border-rule bg-sheet px-4 py-3 shadow-lg">
      <CircleAlert className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden />
      <p className="min-w-0 flex-1 text-sm text-ink">{text}</p>
      <button type="button" onClick={onClose} aria-label="Close" className="grid size-6 shrink-0 place-items-center rounded-md text-ink-3 hover:bg-bench hover:text-ink">
        <X className="size-4" aria-hidden />
      </button>
    </div>,
    document.body,
  );
}
