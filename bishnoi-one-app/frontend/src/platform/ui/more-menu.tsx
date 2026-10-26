"use client";

import { Ellipsis } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";

// A page's less-used actions behind one "More" button (decided 2026-10-26, Hick's law): the
// header keeps its main action and one or two others; import, export, settings and the like
// sit here, grouped, as Zoho keeps them under its "⋯". The panel stays mounted while closed,
// so an item that opens a dialog (Customer sharing) keeps its dialog when the menu closes.

export const MENU_ROW = "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm text-ink hover:bg-bench focus-visible:bg-bench focus-visible:outline-none";

export function MoreMenu({ label = "More actions", children }: { label?: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
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
  return (
    <div ref={box} className="relative">
      {/* Three dots alone, at the far right of the actions (decided 2026-10-26); its name is for screen readers and the tip. */}
      <button
        suppressHydrationWarning
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
        title={label}
        className={`grid size-10 place-items-center rounded-[9px] border border-[#dededa] bg-sheet text-ink shadow-[0_1px_2px_rgba(20,20,20,0.05)] transition-colors hover:border-[#c9c9c5] hover:bg-[#f4f4f2] ${open ? "border-[#c9c9c5] bg-[#f4f4f2]" : ""}`}
      >
        <Ellipsis className="size-5" aria-hidden />
      </button>
      <div
        role="menu"
        hidden={!open}
        onClick={() => setOpen(false)}
        className="absolute top-11 right-0 z-50 w-60 rounded-xl border border-rule bg-white p-1.5 shadow-[0_12px_32px_rgba(20,20,20,0.12)]"
      >
        {children}
      </div>
    </div>
  );
}

/**
 * A page the menu leads to (or a file it downloads). `icon` is a drawn element (<Upload />), not
 * the component: pages drawn on the server can't hand a component to this client one.
 */
export function MenuLink({ href, icon, download, children }: { href: string; icon: ReactNode; download?: boolean; children: ReactNode }) {
  const body = (
    <>
      <span className="inline-flex shrink-0 text-ink-3 [&>svg]:size-4" aria-hidden>
        {icon}
      </span>
      {children}
    </>
  );
  return download ? (
    <a role="menuitem" href={href} download className={MENU_ROW}>
      {body}
    </a>
  ) : (
    <Link role="menuitem" href={href} className={MENU_ROW}>
      {body}
    </Link>
  );
}

/** A line between groups of items. */
export function MenuDivider() {
  return <div role="separator" className="my-1 border-t border-rule" />;
}
