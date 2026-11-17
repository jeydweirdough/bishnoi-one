"use client";

import { useOperatorCompanies } from "@/src/platform/shell/features";
import { switchCompany } from "@/src/one/actions";
import { Check, ChevronDown, ChevronsUpDown, Menu, PanelLeftClose, PanelLeftOpen, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import type { ModuleKey } from "@/src/platform/lib/modules";
import type { MyModule } from "@/src/one/module-switcher";
import { Breadcrumbs } from "./crumbs";
import { useOneMenu } from "@/src/one/menu/context";
import { Icon, type IconName } from "@/src/platform/ui/icons";
import { APP_NAME } from "@/src/platform/lib/labels";

// Every module's sidebar (decided 2026-10-24, benchmarks/surpass.md §1, pattern P15), laid out
// as Bishnoi One Inventory's was (the user's pick) and named the way Zoho names things: the
// Bishnoi One and the company at the top, then
// Home and the main areas, in the order the work goes and with no headings, as Zoho lays it out,
// each opening in place to its pages. Only the area you're in stays open, so the menu stays short;
// closed, an area carries its pages' counts. An area with one page is a plain row. Each module
// builds its menu (src/modules/<module>/.../shell/nav.tsx) and hands it here: fix the sidebar
// here, a menu there.
//
// One menu by work (M4, 2026-11-18): inside the signed-in app the menu is the one built from the account
// (src/one/menu/one-menu.ts, given by app/(app)/layout.tsx), the same on every page whichever module keeps
// it, with no module switcher. A module's own menu only lends its red "not set up" marks, matched by address.

/** What isn't set up yet on a page: how many, and the sentence saying what. */
export type Missing = { count: number; says: string };

/** A page in the menu. `exact`: current only on itself, not on the pages under it. */
export type Step = { href: string; label: string; icon?: string; count?: number; missing?: Missing; also?: string[]; exact?: boolean };

/**
 * A main area and its pages. `section`: kept for the menus' own grouping; not shown.
 * `flow`: its pages are one process, listed in the order the work goes (kept for the menus; not
 * drawn as numbers).
 */
export type Process = { label: string; steps: Step[]; icon?: string; section?: string; flow?: boolean };

type Props = {
  /** The module keeping the page; none on the one app's own pages (Home, Reports). */
  module?: ModuleKey;
  company?: string | null;
  /** The modules this person was given (src/one/mine.ts), for the switcher. */
  mine: MyModule[];
  home?: Step | null;
  processes: Process[];
  /** Setup and administration, at the foot. */
  foot?: Process[];
  /** A small label over the foot, when it holds a different kind of work (the Admin Console's operations, 2026-10-29). */
  footLabel?: string;
  /** Each module draws its own icons by name. */
  icon: (name: string, className: string) => ReactNode;
  rail?: boolean;
  /** The top-right actions (bell, modules, account): beside the menu button on a phone. */
  actions?: ReactNode;
  /** Shown under the menu (Finance's version). */
  footer?: ReactNode;
};

const within = (pathname: string, href: string) => pathname === href || pathname.startsWith(`${href}/`);

/** The page you're on: the most specific match; a page whose address asks for a query wins when the query matches. */
export function currentOf(steps: Step[], pathname: string, search: URLSearchParams | null): Step | undefined {
  let found: Step | undefined;
  let best = -1;
  for (const s of steps) {
    const [path, query] = s.href.split("?");
    const asks = [...new URLSearchParams(query ?? "")];
    let score = -1;
    if (asks.length > 0) {
      if (within(pathname, path) && asks.every(([k, v]) => search?.get(k) === v)) score = 3000 + s.href.length;
    } else if (s.exact ? pathname === path : within(pathname, path)) score = 1000 + path.length;
    for (const a of s.also ?? []) if (within(pathname, a)) score = Math.max(score, 1000 + a.length);
    if (score > best) [found, best] = [s, score];
  }
  return found;
}

/**
 * Whether an area is open: open while you're on one of its pages, and opened or closed by a
 * click in between. The click holds until the page changes, so a closed area opens again when
 * you go into one of its pages.
 */
function useOpen(inside: boolean): [boolean, () => void] {
  const pathname = usePathname();
  const [picked, setPicked] = useState<{ on: string; open: boolean } | null>(null);
  const open = picked?.on === pathname ? picked.open : inside;
  return [open, () => setPicked({ on: pathname, open: !open })];
}

function Count({ n, tone }: { n?: number; tone: "waiting" | "missing" }) {
  if (!n) return null;
  return (
    <span className={`ml-auto inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-md px-1.5 text-[0.6875rem] font-semibold text-white tabular-nums ${tone === "missing" ? "bg-danger" : "bg-hema"}`}>
      {n}
    </span>
  );
}

const rowClass = (current: boolean, open: boolean, nested: boolean) =>
  `flex items-center gap-3 rounded-xl px-3 text-sm transition-colors group-data-[rail=true]/side:justify-center group-data-[rail=true]/side:px-0 ${nested ? "h-8.5" : "h-9"} ${
    current
      ? "bg-mint-2 font-semibold text-sage-deep"
      : open
        ? "bg-mint-2/60 font-semibold text-sage-deep hover:bg-mint-2"
        : "text-ink-2 hover:bg-white/80 hover:text-ink"
  }`;

/** A row with an icon: Home, an area with one page, or an area's own row. */
function IconRow({ href, label, iconName, current, open = false, waiting = 0, missing, icon, onToggle, children }: {
  href: string;
  label: string;
  iconName?: string;
  current: boolean;
  open?: boolean;
  waiting?: number;
  missing?: Missing;
  icon: Props["icon"];
  onToggle?: () => void;
  children?: ReactNode;
}) {
  const red = missing?.count ?? 0;
  const inner = (
    <>
      <span className={`relative inline-flex shrink-0 ${current || open ? "text-sage-deep" : "text-ink-3"}`}>
        {iconName ? icon(iconName, "size-4") : <span className="block size-4" />}
        {(waiting > 0 || red > 0) && <span className="absolute -top-0.5 -right-0.5 size-2 rounded-full bg-danger ring-2 ring-bench" aria-hidden />}
      </span>
      <span className="min-w-0 flex-1 truncate group-data-[rail=true]/side:sr-only">{label}</span>
      <span className="contents group-data-[rail=true]/side:hidden">
        <Count n={red} tone="missing" />
        <Count n={waiting} tone="waiting" />
        {children}
      </span>
      {red > 0 && <span className="sr-only">: {missing?.says}</span>}
      {waiting > 0 && <span className="sr-only">: {waiting} pending</span>}
    </>
  );
  if (onToggle) {
    return (
      <>
        {/* Wide: opens in place. Collapsed to icons there's no room for its pages, so it's a link to the first. */}
        <button suppressHydrationWarning type="button" onClick={onToggle} aria-expanded={open} className={`w-full text-left group-data-[rail=true]/side:hidden ${rowClass(false, open, false)}`}>
          {inner}
        </button>
        <Link href={href} title={label} className={`hidden group-data-[rail=true]/side:flex ${rowClass(current, false, false)}`}>
          {inner}
        </Link>
      </>
    );
  }
  return (
    <Link href={href} aria-current={current ? "page" : undefined} title={missing?.says || label} className={rowClass(current, false, false)}>
      {inner}
    </Link>
  );
}

/** A main area: one row that opens in place to its pages. */
function Area({ area, current, icon }: { area: Process; current: Step | undefined; icon: Props["icon"] }) {
  const inside = current !== undefined && area.steps.includes(current);
  const [open, toggle] = useOpen(inside);
  const only = area.steps.length === 1 ? area.steps[0] : null;
  if (only) {
    return <IconRow href={only.href} label={only.label} iconName={only.icon ?? area.icon} current={only === current} missing={only.missing} icon={icon} />;
  }
  // No waiting counts in the sidebar (decided 2026-10-26, as the CRM): what waits is on Home and the
  // bell. Only a red mark for something not set up yet stays.
  const waiting = 0;
  const missing = area.steps.reduce((m, s) => (s.missing?.count ? { count: m.count + s.missing.count, says: [m.says, s.missing.says].filter(Boolean).join(". ") } : m), { count: 0, says: "" });
  return (
    <div>
      <IconRow href={area.steps[0].href} label={area.label} iconName={area.icon} current={inside} open={open} waiting={open ? 0 : waiting} missing={open ? undefined : missing} icon={icon} onToggle={toggle}>
        <ChevronDown aria-hidden className={`ml-auto size-4 shrink-0 transition-transform ${open ? "rotate-180 text-sage-deep" : "text-ink-3"}`} />
      </IconRow>
      {open && (
        // The area's pages, indented under it, each with its icon; listed in the order the work goes,
        // never numbered (a web app, not a slide).
        <div className="mt-1 mb-1.5 ml-3 animate-reshape space-y-0.5 group-data-[rail=true]/side:hidden" role="group" aria-label={area.label}>
          {area.steps.map((st) => (
            <Link key={st.href} href={st.href} aria-current={st === current ? "page" : undefined} title={st.missing?.says || st.label} className={rowClass(st === current, false, true)}>
              <span className={`inline-flex shrink-0 ${st === current ? "text-sage-deep" : "text-ink-3"}`}>{st.icon ? icon(st.icon, "size-4") : <span className="block size-4" />}</span>
              <span className="min-w-0 flex-1 truncate">{st.label}</span>
              <Count n={st.missing?.count} tone="missing" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Leaves at the foot of the panel, in the brand's colours: sage and mint (the app's own), a faint
 * deep green and the thin orange swoosh of the Bishnoi One mark. Decoration only: behind the menu,
 * never in the way, hidden when the sidebar is collapsed to icons.
 */
function Leaves() {
  return (
    <svg viewBox="0 0 240 230" className="pointer-events-none absolute right-0 bottom-0 left-0 h-auto w-full group-data-[rail=true]/side:hidden" aria-hidden>
      <path d="M-20 230 C 10 150, 70 110, 150 118 C 100 140, 60 180, 40 230 Z" fill="#a8d69b" opacity="0.32" />
      <path d="M30 230 C 50 170, 110 130, 210 150 C 150 165, 110 195, 95 230 Z" fill="#e3eedf" opacity="0.9" />
      <path d="M-30 200 C 20 120, 90 80, 170 70 C 110 100, 50 150, 10 230 L -30 230 Z" fill="#024d17" opacity="0.05" />
      <path d="M110 230 C 130 185, 175 160, 250 168 L 250 230 Z" fill="#a8d69b" opacity="0.22" />
      <path d="M18 214 C 70 150, 140 122, 228 132" fill="none" stroke="#fa4a01" strokeWidth="1.6" strokeLinecap="round" opacity="0.35" />
    </svg>
  );
}

const PANEL_W = 264;

/** The top of the one menu (M4): Bishnoi One and the company; an operator switches company here. */
function OneHeader({ company }: { company?: string | null }) {
  const companies = useOperatorCompanies();
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  useEffect(() => setOpen(false), [pathname]);
  const many = Boolean(companies && companies.length > 1);
  const body = (
    <>
      <img src="/brand/bishnoi-one-mark.png" alt="" width={36} height={36} className="size-9 shrink-0" />
      <span className="min-w-0 flex-1 group-data-[rail=true]/side:sr-only">
        <span className="block truncate text-sm leading-tight font-semibold text-ink">{APP_NAME}</span>
        {company && <span className="block truncate text-meta text-ink-3">{company}</span>}
      </span>
    </>
  );
  if (!many) {
    return (
      <Link href="/" className="flex w-full min-w-0 items-center gap-2.5 rounded-xl p-1.5 text-left hover:bg-sheet group-data-[rail=true]/side:justify-center">
        {body}
      </Link>
    );
  }
  return (
    <div className="relative">
      <button suppressHydrationWarning type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="menu" title="Switch company"
        className="flex w-full min-w-0 items-center gap-2.5 rounded-xl p-1.5 text-left hover:bg-sheet group-data-[rail=true]/side:justify-center">
        {body}
        <ChevronsUpDown className="size-4 shrink-0 text-ink-3 group-data-[rail=true]/side:hidden" aria-hidden />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
          <div role="menu" aria-label="Company" style={{ width: PANEL_W }} className="animate-reshape absolute top-12 left-0 z-50 max-h-[calc(100dvh-6rem)] overflow-y-auto rounded-xl border border-rule bg-white p-1.5 shadow-lg">
            <p className="px-2.5 pt-1.5 pb-1 text-caps text-ink-3 uppercase">Company</p>
            {companies!.map((c) =>
              c.current ? (
                <div key={c.slug} className="flex items-center gap-2 rounded-lg bg-hema-tint px-2.5 py-2 text-sm text-ink" aria-current="true">
                  <span className="min-w-0 flex-1 truncate">{c.name}</span>
                  <Check className="size-4 shrink-0 text-sage-deep" aria-hidden />
                </div>
              ) : (
                <form key={c.slug} action={switchCompany}>
                  <input suppressHydrationWarning type="hidden" name="company" value={c.slug} />
                  <button suppressHydrationWarning type="submit" role="menuitem" className="flex w-full items-center rounded-lg px-2.5 py-2 text-left text-sm text-ink hover:bg-sheet">
                    <span className="min-w-0 flex-1 truncate">{c.name}</span>
                  </button>
                </form>
              ),
            )}
          </div>
        </>
      )}
    </div>
  );
}

/** The one menu in place of a module's own, keeping that module's red "not set up" marks by address. */
function withOneMenu(props: Props, one: ReturnType<typeof useOneMenu>): Props {
  if (!one) return props;
  const marks = new Map<string, Missing>();
  for (const st of [...props.processes, ...(props.foot ?? [])].flatMap((p) => p.steps)) if (st.missing?.count) marks.set(st.href, st.missing);
  const lend = (p: { label: string; icon: string; steps: Step[] }): Process => ({ ...p, steps: p.steps.map((st) => (marks.has(st.href) ? { ...st, missing: marks.get(st.href) } : st)) });
  return {
    ...props,
    home: one.home,
    processes: one.processes.map(lend),
    foot: one.foot.map(lend),
    footLabel: one.foot.length > 0 ? "Administration" : undefined,
    icon: (name, className) => <Icon name={name as IconName} className={className} />,
  };
}

function Menu_({ props, current }: { props: Props; current: Step | undefined }) {
  const { home, processes, foot = [], footLabel, icon } = props;
  const areas = processes.filter((a) => a.steps.length > 0);
  const below = foot.filter((a) => a.steps.length > 0);
  // As Zoho lays it out: no headings, Home then each area in the order the work goes; setup and
  // users at the bottom, under a line.
  return (
    <nav aria-label="Main" className="mt-3 space-y-px">
      {home && <IconRow href={home.href} label={home.label} iconName={home.icon} current={home === current} icon={icon} />}
      {areas.map((a) => (
        <Area key={a.label} area={a} current={current} icon={icon} />
      ))}
      {below.length > 0 && (
        <div className="mt-3 space-y-px border-t border-rule pt-3" role={footLabel ? "group" : undefined} aria-label={footLabel}>
          {footLabel && <p className="px-3 pb-1 text-caps text-ink-3 uppercase group-data-[rail=true]/side:hidden">{footLabel}</p>}
          {below.map((a) => (
            <Area key={a.label} area={a} current={current} icon={icon} />
          ))}
        </div>
      )}
    </nav>
  );
}

function SidebarBody(given: Props) {
  const one = useOneMenu();
  const props = withOneMenu(given, one);
  const pathname = usePathname();
  const search = useSearchParams();
  const [rail, setRail] = useState(props.rail ?? false);
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = openOn === pathname;
  const all = [...(props.home ? [props.home] : []), ...props.processes.flatMap((p) => p.steps), ...(props.foot ?? []).flatMap((p) => p.steps)];
  const current = currentOf(all, pathname, search);
  const group = [...props.processes, ...(props.foot ?? [])].find((p) => current && p.steps.includes(current));
  const place = current ? (group && current !== props.home ? `${group.label} · ${current.label}` : current.label) : null;
  const companies = useOperatorCompanies();

  function toggleRail() {
    const next = !rail;
    setRail(next);
    // A cookie, so the next page is drawn the same way from the start; every module reads the same one.
    document.cookie = `bishnoi_nav=${next ? "rail" : "full"}; path=/; max-age=31536000; samesite=lax`;
  }

  return (
    <>
      {/* Company / App / Area / Page at the top of the page (2026-11-01), into the frame's slot. */}
      <Breadcrumbs module={one ? undefined : props.module} company={props.company} companies={companies} mine={props.mine} area={group} page={current} home={props.home} />
      <aside data-rail={rail} className="group/side sticky top-0 hidden h-dvh w-[16.5rem] overflow-x-hidden overflow-y-auto p-3 transition-[width] duration-200 data-[rail=true]:w-[4.75rem] data-[rail=true]:p-2 lg:block print:!hidden">
       <div className="relative flex min-h-full flex-col justify-between overflow-hidden rounded-2xl border border-mint-2 bg-linear-to-b from-mint via-white to-white px-2.5 pt-3 pb-40 shadow-[0_1px_3px_rgba(20,20,20,0.05)] group-data-[rail=true]/side:px-1.5 group-data-[rail=true]/side:pb-4">
        <Leaves />
        <div className="relative">
          <div className="flex items-start gap-1 group-data-[rail=true]/side:flex-col group-data-[rail=true]/side:items-center">
            <div className="min-w-0 flex-1 group-data-[rail=true]/side:w-full">
              <OneHeader company={props.company} />
            </div>
            <button
              suppressHydrationWarning
              type="button"
              onClick={toggleRail}
              aria-label={rail ? "Expand sidebar" : "Collapse sidebar"}
              title={rail ? "Expand sidebar" : "Collapse sidebar"}
              className="mt-1.5 grid size-8 shrink-0 place-items-center rounded-full text-ink-3 hover:bg-sheet hover:text-ink group-data-[rail=true]/side:mt-2"
            >
              {rail ? <PanelLeftOpen className="size-4" aria-hidden /> : <PanelLeftClose className="size-4" aria-hidden />}
            </button>
          </div>
          <Menu_ props={props} current={current} />
        </div>
        {props.footer && <div className="relative mt-6 group-data-[rail=true]/side:hidden">{props.footer}</div>}
       </div>
      </aside>

      {/* Phone and tablet: a top bar with the module, the actions, and a menu saying where you are. */}
      <div className="sticky top-0 z-30 bg-bench/95 backdrop-blur lg:hidden print:hidden">
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <div className="w-44 min-w-0 shrink">
            <OneHeader company={props.company} />
          </div>
          <div className="flex min-w-0 items-center gap-1">
            {props.actions}
            <button
              suppressHydrationWarning
              type="button"
              onClick={() => setOpenOn(open ? null : pathname)}
              aria-expanded={open}
              aria-controls="phone-menu"
              className="inline-flex h-10 min-w-0 items-center gap-2 rounded-lg pr-2 pl-3 text-ink hover:bg-sheet"
            >
              {place && <span className="hidden min-w-0 truncate text-meta font-semibold text-ink-2 sm:inline">{place}</span>}
              {open ? <X className="size-5 shrink-0" aria-hidden /> : <Menu className="size-5 shrink-0" aria-hidden />}
              <span className="sr-only">{open ? "Close menu" : "Open menu"}</span>
            </button>
          </div>
        </div>
        {open && (
          <div id="phone-menu" className="animate-reshape max-h-[calc(100dvh-4.5rem)] overflow-y-auto border-t border-rule px-3 pt-1 pb-5">
            <Menu_ props={props} current={current} />
            {props.footer && <div className="mt-4 border-t border-rule pt-3">{props.footer}</div>}
          </div>
        )}
      </div>
    </>
  );
}

/** One module's sidebar: see the comment at the top. */
export function Sidebar(props: Props) {
  // The query decides the current step on a few pages (Inventory's filtered lists); reading it needs a boundary.
  return (
    <Suspense fallback={<aside className="sticky top-0 hidden h-dvh w-[16.5rem] lg:block" />}>
      <SidebarBody {...props} />
    </Suspense>
  );
}
