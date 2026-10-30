"use client";

import { Check, ChevronDown, LayoutGrid } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { MODULES, moduleOfPath } from "@/src/platform/lib/modules";

/** A module this person has, as the switcher shows it. */
export type MyModule = { key: string; oldUrl: string | null };

/**
 * Which module you're in, and the others you have, one click away (decided
 * 2026-10-23: one app, so switching is a page change, not another site).
 */
export function ModuleSwitcher({ mine, compact = false }: { mine: MyModule[]; compact?: boolean }) {
  const pathname = usePathname();
  const here = moduleOfPath(pathname);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => box.current && !box.current.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  // The consoles first (the Admin Console, then Operations), for those who have them: where they start.
  const rank = (k: string) => (k === "platform" ? 0 : k === "operations" ? 1 : 2);
  const list = MODULES.filter((m) => mine.some((x) => x.key === m.key)).sort((a, b) => rank(a.key) - rank(b.key));
  return (
    <div ref={box} className="relative">
      {compact ? (
        // As the old app launcher: a grid at the top right, your modules under it.
        <button suppressHydrationWarning
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-haspopup="menu"
          aria-label="Your modules"
          title="Your modules"
          className={`grid size-10 place-items-center rounded-lg text-ink-2 transition-colors hover:bg-sheet hover:text-ink ${open ? "bg-sheet text-ink" : ""}`}
        >
          <LayoutGrid className="size-5" aria-hidden />
        </button>
      ) : (
      <button suppressHydrationWarning
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="inline-flex h-9 items-center gap-2 rounded-full border border-rule bg-white pr-3 pl-1.5 text-sm font-medium text-ink transition-colors hover:border-ink"
      >
        {here ? (
          <span className="grid size-6 place-items-center rounded-full" style={{ background: here.tint, color: here.ink }}>
            <here.icon className="size-3.5" aria-hidden />
          </span>
        ) : (
          <span className="grid size-6 place-items-center rounded-full bg-bench text-ink-2">
            <LayoutGrid className="size-3.5" aria-hidden />
          </span>
        )}
        {here ? here.label : "All modules"}
        <ChevronDown className="size-4 text-ink-3" aria-hidden />
      </button>
      )}
      {open && (
        <div role="menu" className={`absolute top-11 z-50 ${compact ? "right-0" : "left-0"} w-72 rounded-2xl border border-rule bg-white p-2 shadow-[0_12px_32px_rgba(20,20,20,0.12)]`}>
          {list.length === 0 && <p className="px-2.5 py-2 text-meta text-ink-3">No modules given to your account yet.</p>}
          {list.map((m) => {
            const old = mine.find((x) => x.key === m.key)?.oldUrl;
            const body = (
              <>
                <span className="grid size-8 place-items-center rounded-xl" style={{ background: m.tint, color: m.ink }}>
                  <m.icon className="size-4" aria-hidden />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{m.label}</span>
                  <span className="block truncate text-meta text-ink-3">{m.status === "soon" ? "Coming soon" : m.status === "moving" ? "Opens its current app for now" : m.blurb}</span>
                </span>
                {here?.key === m.key && <Check className="size-4 text-ink-3" aria-hidden />}
              </>
            );
            const cls = "flex items-center gap-3 rounded-xl px-2.5 py-2 text-sm text-ink hover:bg-bench";
            if (m.status === "soon") return <div key={m.key} role="menuitem" aria-disabled className={`${cls} opacity-60 hover:bg-transparent`}>{body}</div>;
            if (m.status === "moving" && old) return <a key={m.key} role="menuitem" href={old} className={cls}>{body}</a>;
            return <Link key={m.key} role="menuitem" href={m.path} className={cls}>{body}</Link>;
          })}
        </div>
      )}
    </div>
  );
}
