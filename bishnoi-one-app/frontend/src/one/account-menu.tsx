"use client";

import { Check, ChevronDown, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Avatar } from "@/src/platform/ui/avatar";
import { signOut, switchCompany } from "./actions";

type Company = { slug: string; name: string; current: boolean };

/** One of the module's own pages for you (your profile there, your mailbox), listed under your name. */
export type AccountLink = { href: string; label: string };

/**
 * Who is signed in, the company they're working in (and the others they can
 * move to), their own pages in the module they're in, and sign out. `compact`:
 * just the picture, at the top right of a module's pages (as before the one app).
 */
export function AccountMenu({ id, name, email, companies, links = [], compact = false }: { id: string; name: string; email: string; companies: Company[]; links?: AccountLink[]; compact?: boolean }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const current = companies.find((c) => c.current);

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

  return (
    <div ref={box} className="relative">
      <button suppressHydrationWarning
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={compact ? `${name}: your account` : undefined}
        title={compact ? name : undefined}
        className={compact ? "grid size-10 place-items-center rounded-full transition-colors hover:bg-sheet" : "inline-flex h-10 items-center gap-2.5 rounded-full py-1 pr-2.5 pl-1 transition-colors hover:bg-bench"}
      >
        <Avatar name={name} id={id} size="sm" />
        {!compact && (
          <>
            <span className="hidden min-w-0 text-left sm:block">
              <span className="block max-w-[12rem] truncate text-sm font-medium text-ink">{name}</span>
              {current && <span className="block max-w-[12rem] truncate text-meta text-ink-3">{current.name}</span>}
            </span>
            <ChevronDown className="size-4 text-ink-3" aria-hidden />
          </>
        )}
      </button>
      {open && (
        <div role="menu" className="absolute top-12 right-0 z-50 w-72 rounded-2xl border border-rule bg-white p-2 shadow-[0_12px_32px_rgba(20,20,20,0.12)]">
          <div className="px-2.5 py-2">
            <p className="truncate text-sm font-medium text-ink">{name}</p>
            <p className="truncate text-meta text-ink-3">{email}</p>
            {compact && current && <p className="mt-0.5 truncate text-meta text-ink-3">{current.name}</p>}
          </div>
          {links.length > 0 && (
            <>
              <div className="my-1.5 border-t border-rule" />
              {links.map((l) => (
                <Link key={l.href} href={l.href} role="menuitem" className="flex items-center rounded-xl px-2.5 py-2 text-sm text-ink hover:bg-bench">
                  {l.label}
                </Link>
              ))}
            </>
          )}
          {companies.length > 1 && (
            <>
              <div className="my-1.5 border-t border-rule" />
              <p className="px-2.5 pt-1 pb-1.5 text-meta font-semibold text-ink-3">Company</p>
              {companies.map((c) =>
                c.current ? (
                  <div key={c.slug} className="flex items-center gap-2 rounded-xl px-2.5 py-2 text-sm text-ink">
                    {c.name}
                    <Check className="ml-auto size-4 text-ink-3" aria-hidden />
                  </div>
                ) : (
                  <form key={c.slug} action={switchCompany}>
                    <input suppressHydrationWarning type="hidden" name="company" value={c.slug} />
                    <button suppressHydrationWarning type="submit" role="menuitem" className="flex w-full items-center rounded-xl px-2.5 py-2 text-left text-sm text-ink hover:bg-bench">
                      {c.name}
                    </button>
                  </form>
                ),
              )}
            </>
          )}
          <div className="my-1.5 border-t border-rule" />
          <form action={signOut}>
            <button suppressHydrationWarning type="submit" role="menuitem" className="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left text-sm text-ink hover:bg-bench">
              <LogOut className="size-4 text-ink-3" aria-hidden />
              Sign out
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
