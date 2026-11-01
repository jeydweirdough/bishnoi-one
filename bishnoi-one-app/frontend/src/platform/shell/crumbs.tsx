"use client";

import { Check, ChevronsUpDown } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { switchCompany } from "@/src/one/actions";
import { MODULES, type ModuleKey } from "@/src/platform/lib/modules";
import type { MyModule } from "@/src/one/module-switcher";

// Where you are, at the top of every page (2026-11-01, as Coolify lays it out): Company ⇕ / App ⇕ / Area ⇕ / Page.
// Each part is also a switcher: another company (operators), another app, another page of the same area. Drawn by
// the shared sidebar, which knows the app, its areas and the page you're on, into the slot in each frame's top bar.

const SLOT = "bishnoi-crumbs";

/** Where the breadcrumbs go: the left of a frame's top bar. */
export function CrumbsSlot() {
  return <nav id={SLOT} aria-label="Where you are" className="min-w-0 flex-1" />;
}

type Item = { key: string; label: string; sub?: string; href?: string; current?: boolean; form?: { company: string } };
type Step = { href: string; label: string };

function Crumb({ label, title, items, footer }: { label: ReactNode; title: string; items: Item[]; footer?: ReactNode }) {
  const pathname = usePathname();
  const button = useRef<HTMLButtonElement>(null);
  const [at, setAt] = useState<{ top: number; left: number } | null>(null);
  useEffect(() => setAt(null), [pathname]);
  useEffect(() => {
    if (!at) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && (setAt(null), button.current?.focus());
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [at]);

  function toggle() {
    if (at) return setAt(null);
    const r = button.current?.getBoundingClientRect();
    if (r) setAt({ top: r.bottom + 6, left: Math.max(8, r.left) });
  }

  return (
    <>
      <button
        ref={button}
        type="button"
        onClick={toggle}
        aria-haspopup="menu"
        aria-expanded={at !== null}
        title={title}
        className="inline-flex min-w-0 items-center gap-1 rounded-md px-1.5 py-1 text-sm font-medium text-ink hover:bg-sheet"
      >
        <span className="truncate">{label}</span>
        <ChevronsUpDown className="size-3.5 shrink-0 text-ink-3" aria-hidden />
      </button>
      {at && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setAt(null)} aria-hidden />
          <div role="menu" aria-label={title} style={{ top: at.top, left: at.left }} className="animate-reshape fixed z-50 max-h-[calc(100dvh-6rem)] w-64 overflow-y-auto rounded-xl border border-rule bg-white p-1.5 shadow-lg">
            <p className="px-2.5 pt-1.5 pb-1 text-caps text-ink-3 uppercase">{title}</p>
            {items.map((i) => {
              const inner = (
                <>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm text-ink">{i.label}</span>
                    {i.sub && <span className="block truncate text-meta text-ink-3">{i.sub}</span>}
                  </span>
                  {i.current && <Check className="size-4 shrink-0 text-sage-deep" aria-hidden />}
                </>
              );
              const cls = `flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left ${i.current ? "bg-hema-tint" : "hover:bg-sheet"}`;
              if (i.form) {
                return i.current ? (
                  <div key={i.key} className={cls} aria-current="true">
                    {inner}
                  </div>
                ) : (
                  <form key={i.key} action={switchCompany}>
                    <input type="hidden" name="company" value={i.form.company} />
                    <button type="submit" role="menuitem" className={cls}>
                      {inner}
                    </button>
                  </form>
                );
              }
              return (
                <Link key={i.key} role="menuitem" href={i.href ?? "#"} aria-current={i.current ? "true" : undefined} className={cls}>
                  {inner}
                </Link>
              );
            })}
            {footer}
          </div>
        </>
      )}
    </>
  );
}

const Slash = () => (
  <span className="px-0.5 text-ink-3" aria-hidden>
    /
  </span>
);

/**
 * Company ⇕ / App ⇕ / Area ⇕ / Page, put into the frame's slot. `area` and `page` come from the sidebar (the
 * page you're on, and the area it sits in); `companies` only for operators, who work in any company.
 */
export function Breadcrumbs({ module, company, companies, mine, area, page, home }: {
  module: ModuleKey;
  company?: string | null;
  companies: { name: string; slug: string; current: boolean }[] | null;
  mine: MyModule[];
  area: { label: string; steps: Step[] } | undefined;
  page: Step | undefined;
  home: Step | null | undefined;
}) {
  const pathname = usePathname();
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  useEffect(() => setSlot(document.getElementById(SLOT)), [pathname]);
  if (!slot) return null;

  const here = MODULES.find((m) => m.key === module)!;
  const rank = (k: string) => (k === "platform" ? 0 : k === "operations" ? 1 : 2);
  const apps = MODULES.filter((m) => mine.some((x) => x.key === m.key)).sort((a, b) => rank(a.key) - rank(b.key));
  const onHome = !page || page === home;
  // An area with one page reads as that page: no area switcher before it.
  const showArea = !onHome && area && area.steps.length > 1;

  return createPortal(
    <span className="flex min-w-0 flex-wrap items-center gap-0.5">
      {company &&
        (companies && companies.length > 1 ? (
          <Crumb label={company} title="Company" items={companies.map((c) => ({ key: c.slug, label: c.name, current: c.current, form: { company: c.slug } }))} />
        ) : (
          <span className="truncate px-1.5 py-1 text-sm font-medium text-ink-2">{company}</span>
        ))}
      {company && <Slash />}
      <Crumb
        label={here.label}
        title="Your apps"
        items={apps.map((m) => {
          const given = mine.find((x) => x.key === m.key);
          return { key: m.key, label: m.label, sub: m.status === "soon" ? "Coming soon" : m.blurb, href: m.status === "live" ? m.path : (given?.oldUrl ?? m.path), current: m.key === module };
        })}
        footer={
          <Link href="/" className="mt-1 block border-t border-rule px-2.5 pt-2.5 pb-1.5 text-meta text-ink-2 hover:text-ink">
            All modules
          </Link>
        }
      />
      {showArea && (
        <>
          <Slash />
          <Crumb label={area.label} title={area.label} items={area.steps.map((s) => ({ key: s.href, label: s.label, href: s.href, current: s === page }))} />
        </>
      )}
      {page && !onHome && !(showArea && area.label === page.label) && (
        <>
          <Slash />
          {pathname === page.href.split("?")[0] ? (
            <span className="truncate px-1.5 py-1 text-sm font-semibold text-ink" aria-current="page">
              {page.label}
            </span>
          ) : (
            <Link href={page.href} className="truncate rounded-md px-1.5 py-1 text-sm font-semibold text-ink hover:bg-sheet">
              {page.label}
            </Link>
          )}
        </>
      )}
    </span>,
    slot,
  );
}
