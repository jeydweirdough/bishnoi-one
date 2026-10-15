"use client";

import { ChevronRight, Menu, PanelLeftClose, PanelLeftOpen, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Icon, moduleIcon, type IconName } from "../ui/icons";
import { THIS_APP, appLabel, appOf, appUrl, href as appHref, isOurs, moduleBase, platformHome, thisAppLabel } from "../lib/apps";
import { adminPagesFor } from "../lib/access";
import { APP_NAME } from "../lib/labels";
import type { Me, ModuleAccess } from "../lib/types";

// The one place everyone finds their way.
//
// A sales division is not a section of the app: Overview, Customers, Follow-ups
// and Retention are the same pages whichever division a record is in, and their
// contents merge. So they are five plain links, the same for someone in one
// division as for someone in six.
//
// A department is different. Inventory's pages (stock, transfers, purchasing)
// are nothing like Finance's (approvals, letters, payments), so a department
// really is a section, and opens to show its own.

/** Whether the desktop sidebar is collapsed to its icons. */
const RailContext = createContext(false);

type Page = {
  href: string;
  label: string;
  icon: IconName;
  also?: string[];
  /** Settings only: who reaches this page. The default is an Admin. A
   *  page offered to someone the API will then refuse is worse than no page,
   *  so these mirror the gates in app/deps.py rather than approximating them. */
  reach?: (me: Me) => boolean;
  /** Its sibling pages, which used to be tabs across the top of each: the row
   *  opens to them, indented under it, while you're on one of them. */
  subpages?: SubPage[];
};
/** A page of a page. It may carry a query (/orders?status=issued) when that is what makes it a page of its own. */
type SubPage = { href: string; label: string };
type PageGroup = { label?: string; pages: Page[] };

// The three keys to Settings, and what each unlocks.
//
// `manage` runs the company: every screen, business rules included. `recover`
// is the narrower one a Developer Admin holds — the company record, its
// accounts, the apps it reaches and the log — for when something is broken.
// Owning the company is neither: it is set on the membership, so no admin can
// grant it to themselves.
const manages = (me: Me) => me.canManageSettings;
/** Reachable when the company is broken. An Admin holds this too. */
const recovers = (me: Me) => me.canManageSettings || me.canRecover;
/** What the company *is*. The owner's, or whoever was trusted with recovery —
 *  never a plain Admin, who runs the company without deciding it. */
const ownsOrRecovers = (me: Me) => me.isOwner || me.canRecover;
/** Above every company, so not a company's to grant. */
const develops = (me: Me) => me.isDeveloperAdmin;

/** The CRM's own pages. Each shows only for a role that may open it. Six at
 *  most: each is a place, and what belongs to a place is a tab inside it. */
function crmPages(me: Me): Page[] {
  const may = (permission: string) => me.permissions?.includes(permission) ?? false;
  if (THIS_APP === "crm" && me.isOwner) {
    return [
      { href: "/", label: "Dashboard", icon: "overview" },
      { href: "/products", label: "Products", icon: "products" as const, also: ["/promos", "/bundles", "/prices"] },
    ];
  }
  return [
    // The CRM opens on Home; in the shell that screen is a page of its
    // own, because the shell's own root is the dashboard.
    { href: THIS_APP === "crm" ? "/" : "/overview", label: "Home", icon: "home" },
    // Customers are companies and the contacts in them.
    { href: "/companies", label: "Customers", icon: "customers", also: ["/contacts", "/customers"] },
    ...(may("quotes.view") ? [{ href: "/quotes", label: "Quotes", icon: "quotes" as const }] : []),
    // To do and history; follow-ups are its To do list now.
    { href: "/activities", label: "Activities", icon: "activity", also: ["/follow-ups"] },
    { href: "/retention", label: "Retention", icon: "retention" },
    // Products, promos, bundles, and a team's own prices, as tabs.
    ...(may("products.view") || may("products.prices")
      ? [{ href: may("products.view") ? "/products" : "/prices", label: "Products", icon: "products" as const, also: ["/promos", "/bundles", "/prices", "/products"] }]
      : []),
  ];
}

/** How many things are waiting on this person, by kind (the API's alerts,
 *  already limited to what their role may act on). */
export type Waiting = Record<string, number>;

/** How many things aren't set up yet, by kind (the API's /inventory/unset):
 *  only the kinds this person can fix, so every red mark is one they can act on. */
export type Unset = Record<string, number>;

/** What each kind's red mark says when pointed at. */
const UNSET_SAYS: Record<string, (n: number) => string> = {
  productPrices: (n) => `${n} ${n === 1 ? "product has" : "products have"} no selling price or cost`,
};

type Place = Page & {
  /** Any of these, and they may open it. */
  sees: string[];
  /** The alerts that count as waiting on them here. */
  waiting?: string[];
  /** The things not set up yet that are fixed here. */
  unset?: string[];
};

/** A main page and the pages that belong to it, e.g. Stock: on hand, batches, serials, movements. */
type Area = { label: string; icon: IconName; places: Place[] };

type Section = { label: string; areas: Area[] };

/**
 * Inventory's sidebar, laid out the way ERP systems (SAP, NetSuite, Odoo,
 * Zoho Inventory) lay out theirs: a few main areas, each opening in place to
 * its own pages, so batches and serials sit inside Stock rather than beside it.
 * An area with only one page this role may open is a plain row with that
 * page's name. Each page says how many things wait on them there.
 */
function inventoryNav(me: Me): { home: Page | null; sections: Section[] } {
  const may = (permission: string) => me.permissions?.includes(permission) ?? false;
  const sections: Section[] = [
    {
      label: "General",
      areas: [{ label: "Reports", icon: "report", places: [{ href: "/reports", label: "Reports", icon: "report", sees: ["reports.view"] }] }],
    },
    {
      label: "Operations",
      areas: [
        {
          label: "Purchasing",
          icon: "purchaseOrders",
          places: [
            { href: "/purchase-orders", label: "Purchase orders", icon: "purchaseOrders", also: ["/backorders"], sees: ["purchasing.view"], waiting: may("purchasing.approve") ? ["drafts"] : [] },
            { href: "/receipts", label: "Receiving", icon: "receiving", sees: ["receiving.view"], waiting: ["receiving"] },
            { href: "/suppliers", label: "Suppliers", icon: "suppliers", sees: ["suppliers.view"] },
          ],
        },
        {
          label: "Stock",
          icon: "stock",
          places: [
            { href: "/stock", label: "Stock on hand", icon: "stock", sees: ["stock.view"] },
            { href: "/batches", label: "Batches and expiry", icon: "batches", sees: ["stock.view"] },
            { href: "/serials", label: "Serial numbers", icon: "serials", sees: ["stock.view"] },
            { href: "/movements", label: "Stock movements", icon: "history", sees: ["stock.view"] },
            { href: "/warehouses", label: "Warehouses", icon: "warehouses", sees: ["warehouses.view"] },
          ],
        },
        {
          label: "Fulfillment",
          icon: "issuance",
          places: [
            // One board for every kind of order (the kinds are its filter, each with its own form).
            { href: "/orders", label: "Orders", icon: "issuance", also: ["/reservations"], sees: ["orders.view"], waiting: ["issue"] },
            { href: "/transfers", label: "Transfers", icon: "transfers", sees: ["transfers.view"], waiting: ["transfer_requests", "dispatch", "transit"] },
          ],
        },
        {
          label: "Stock control",
          icon: "adjustments",
          places: [
            { href: "/adjustments", label: "Adjustments", icon: "adjustments", sees: ["adjustments.view"], waiting: ["adjustments"] },
            { href: "/counts", label: "Stock counts", icon: "counts", sees: ["counts.view"], waiting: ["counts"] },
          ],
        },
      ],
    },
    {
      label: "Master data",
      areas: [
        {
          label: "Products",
          icon: "products",
          places: [
            { href: "/products", label: "All products", icon: "products", sees: ["products.view"], unset: ["productPrices"] },
            { href: "/catalog/categories", label: "Categories", icon: "categories", sees: ["products.view"] },
            { href: "/catalog/brands", label: "Brands", icon: "brands", sees: ["products.view"] },
            { href: "/catalog/units", label: "Units", icon: "units", sees: ["products.view"] },
          ],
        },
      ],
    },
    {
      label: "Administration",
      areas: [
        {
          label: "Users and access",
          icon: "people",
          places: [
            { href: "/admin/users", label: "Users", icon: "people", sees: ["admin.users"] },
            { href: "/admin/roles", label: "Roles and permissions", icon: "roles", sees: ["admin.roles"] },
            { href: "/admin/audit", label: "Audit log", icon: "auditLog", sees: ["admin.audit"] },
          ],
        },
      ],
    },
  ];
  const home: Page | null = may("dashboard.view") ? { href: "/", label: "Home", icon: "home" } : null;
  return {
    home,
    sections: sections
      .map((s) => ({
        ...s,
        areas: s.areas.map((a) => ({ ...a, places: a.places.filter((p) => p.sees.some(may)) })).filter((a) => a.places.length > 0),
      }))
      .filter((s) => s.areas.length > 0 || (s.label === "General" && home !== null)),
  };
}

/** Every page in the sidebar, areas opened out. */
const placesOf = (sections: Section[]) => sections.flatMap((s) => s.areas.flatMap((a) => a.places));

/**
 * The row you're on: the most specific one the address is in. A query counts,
 * so Orders to issue (/orders?status=confirmed,picking) is on rather than
 * Customer orders when the address asks for those; a record's own page
 * (/orders/123) falls back to the row its path starts with.
 */
function currentPlace(places: Place[], pathname: string, search: URLSearchParams): Place | undefined {
  let found: Place | undefined;
  let best = -1;
  for (const p of places) {
    const [path, query] = p.href.split("?");
    const asks = [...new URLSearchParams(query ?? "")];
    let score = -1;
    if (within(pathname, path) && asks.length > 0 && asks.every(([k, v]) => search.get(k) === v)) score = 2000 + p.href.length;
    else if ((p.also ?? []).some((a) => within(pathname, a))) score = 1500;
    else if (asks.length === 0 && within(pathname, path)) score = 1000 + path.length;
    if (score > best) [found, best] = [p, score];
  }
  return found;
}

/**
 * How many things in a place aren't set up yet: red, because until they are
 * something doesn't work (a product with no price sells for nothing).
 */
function UnsetMark({ place, unset }: { place: Place; unset: Unset }) {
  const found = (place.unset ?? []).filter((key) => unset[key]);
  const count = found.reduce((n, key) => n + unset[key], 0);
  if (!count) return null;
  const says = found.map((key) => UNSET_SAYS[key]?.(unset[key]) ?? "").filter(Boolean).join(". ");
  return (
    <span title={says} className="ml-auto inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-md bg-danger px-1.5 text-[0.6875rem] font-semibold text-white tabular-nums">
      {count}
      <span className="sr-only"> not set up: {says}</span>
    </span>
  );
}

function InventoryLinks({ me, waiting, unset }: { me: Me; waiting: Waiting; unset: Unset }) {
  const pathname = usePathname();
  const search = useSearchParams();
  const { home, sections } = inventoryNav(me);
  const atHome = pathname === "/" || within(pathname, "/alerts");
  const here = atHome ? undefined : currentPlace(placesOf(sections), pathname, search);
  const count = (p: Place) => (p.waiting ?? []).reduce((n, key) => n + (waiting[key] ?? 0), 0);
  return (
    <nav aria-label="Main">
      {sections.map((s, i) => (
        <Group key={s.label} label={s.label} dense first={i === 0}>
          {s.label === "General" && home && (
            <Row href={home.href} icon={home.icon} current={atHome} dense>
              {home.label}
            </Row>
          )}
          {s.areas.map((a) =>
            a.places.length === 1 ? (
              <Row key={a.label} href={a.places[0].href} icon={a.places[0].icon} current={a.places[0] === here} dense count={count(a.places[0])} trailing={<UnsetMark place={a.places[0]} unset={unset} />}>
                {a.places[0].label}
              </Row>
            ) : (
              <AreaEntry key={a.label} area={a} here={here} count={count} unset={unset} />
            ),
          )}
        </Group>
      ))}
    </nav>
  );
}

/**
 * A main area: one row that opens in place to its pages, open already while
 * you're on one of them. Closed, it carries its pages' counts; open, each page
 * carries its own. In the narrow rail it is a link to its first page.
 */
function AreaEntry({ area, here, count, unset }: { area: Area; here: Place | undefined; count: (p: Place) => number; unset: Unset }) {
  const inside = here !== undefined && area.places.includes(here);
  const [open, toggle] = useOpen(inside);
  const waitingHere = area.places.reduce((n, p) => n + count(p), 0);
  const unsetHere: Place = { href: area.places[0].href, label: area.label, icon: area.icon, sees: [], unset: area.places.flatMap((p) => p.unset ?? []) };
  return (
    <div>
      <Row
        href={area.places[0].href}
        icon={area.icon}
        current={false}
        open={open || inside}
        onToggle={toggle}
        dense
        count={open ? 0 : waitingHere}
        trailing={
          <>
            {!open && <UnsetMark place={unsetHere} unset={unset} />}
            <ChevronRight aria-hidden className={`ml-auto size-3.5 shrink-0 text-ink-3 transition-transform ${open ? "rotate-90" : ""}`} />
          </>
        }
      >
        {area.label}
      </Row>
      {open && (
        // The guide line sits under the area's icon, so the pages read as its own.
        <div className="mt-px mb-1 ml-[1.1875rem] animate-reshape space-y-px border-l border-rule pl-2 group-data-[rail=true]/side:hidden" role="group" aria-label={area.label}>
          {area.places.map((p) => (
            <Row key={p.href} href={p.href} nested current={p === here} trailing={<SubMarks count={count(p)} place={p} unset={unset} />}>
              {p.label}
            </Row>
          ))}
        </div>
      )}
    </div>
  );
}

/** A page under an area has no icon to put a dot on, so its count is a small number at the end. */
function SubMarks({ count, place, unset }: { count: number; place: Place; unset: Unset }) {
  return (
    <>
      <UnsetMark place={place} unset={unset} />
      {count > 0 && (
        <span className="ml-auto inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-md bg-hema px-1.5 text-[0.6875rem] font-semibold text-white tabular-nums">
          {count}
          <span className="sr-only"> waiting on you</span>
        </span>
      )}
    </>
  );
}

/**
 * Whether a row is open: open while you're on one of its pages, and opened or
 * closed by a click in between. The click holds until the page changes, so a
 * closed row opens again when you go into one of its pages.
 */
function useOpen(onIt: boolean): [boolean, () => void] {
  const pathname = usePathname();
  const [picked, setPicked] = useState<{ on: string; open: boolean } | null>(null);
  const open = picked?.on === pathname ? picked.open : onIt;
  return [open, () => setPicked({ on: pathname, open: !open })];
}

function modulePages(m: ModuleAccess): Page[] {
  const base = moduleBase(m.key);
  // In the module's own app the prefix is empty, so its root is plain "/".
  const root = base || "/";
  if (m.key === "finance") {
    return [
      { href: root, label: "Overview", icon: "overview" },
      { href: `${base}/approvals`, label: "Approvals", icon: "approvals" },
      { href: `${base}/letters`, label: "Guarantee letters", icon: "letters" },
      { href: `${base}/payments`, label: "Letter payments", icon: "payments" },
    ];
  }
  return [{ href: root, label: "Overview", icon: "overview" }];
}

// Settings' pages: the company itself, then who can do what, then the business
// rules the app enforces.
const SETTINGS: PageGroup[] = [
  // The company itself first: it is who everything below belongs to, and which
  // other applications it runs.
  {
    pages: [
      // The platform first for whoever sits above it: which company you are
      // looking at decides what everything below this line means.
      { href: "/platform", label: "Companies", icon: "companies", reach: develops },
      { href: "/settings/company", label: "Company", icon: "company", reach: ownsOrRecovers },
      { href: "/settings/apps", label: "Apps", icon: "apps", reach: recovers },
    ],
  },
  {
    label: "Access",
    pages: [
      { href: "/settings/people", label: "People", icon: "people", reach: recovers },
      { href: "/settings/roles", label: "Roles and permissions", icon: "roles" },
      { href: "/settings/teams", label: "Teams", icon: "teams" },
      { href: "/settings/audit", label: "Audit log", icon: "auditLog", reach: recovers },
    ],
  },
  {
    label: "Business rules",
    pages: [
      { href: "/settings/lists", label: "Lists", icon: "lists" },
      { href: "/settings/pricing", label: "Pricing", icon: "pricing" },
      { href: "/settings/money", label: "Money and formats", icon: "money" },
      { href: "/settings/orders", label: "Orders", icon: "orders" },
      { href: "/settings/retention", label: "Retention", icon: "retention" },
      { href: "/settings/goals", label: "Goals", icon: "goals" },
    ],
  },
];

/**
 * The settings pages this person may open, in their groups.
 *
 * Settings is the Admin app's, and these paths are the same in it as they are
 * in the shell, so `href` is all that is needed: a path while you are already
 * in Admin, Admin's full address from anywhere else. "Companies" is the odd one
 * out — it is Platform's screen sitting in Admin's menu.
 */
function settingsFor(me: Me): PageGroup[] {
  return SETTINGS.map((g) => ({
    ...g,
    pages: g.pages
      .filter((p) => (p.reach ?? manages)(me))
      // "Companies" is Platform's screen, not Admin's. The shell keeps it in
      // this menu, where it has always been, because the shell serves it; any
      // other app lists Platform among the apps instead.
      .filter((p) => !THIS_APP || p.href !== "/platform")
      .map((p) =>
        p.href === "/platform"
          ? { ...p, href: platformHome() }
          : { ...p, href: appHref("exec", p.href) },
      ),
  })).filter((g) => g.pages.length > 0);
}

/**
 * Whether the sidebar offers the other Bishnoi One apps.
 *
 * Off while each app is being built on its own: a panel of links into apps that
 * are half-built, or not built at all, is noise in the one place a person goes
 * to find their way. Everything behind it still works — `elsewhere` is still
 * assembled, the panel still renders — so turning it back on is this line.
 */
const SHOW_OTHER_APPS = false;

const within = (pathname: string, href: string) => pathname === href || pathname.startsWith(`${href}/`);

/** A link `href` turned into another app's address, so it needs a real page load. */
const isAway = (href: string) => href.startsWith("http://") || href.startsWith("https://");

/** Whether a page is the one open: a section's overview only on itself, other pages on anything below them. */
function isCurrent(page: Page, pathname: string, overview: boolean): boolean {
  if (overview) return pathname === page.href;
  return within(pathname, page.href) || (page.also ?? []).some((a) => within(pathname, a));
}

function Row({
  href,
  icon,
  current,
  open = false,
  nested = false,
  dense = false,
  trailing,
  count = 0,
  onToggle,
  children,
}: {
  href: string;
  /** Left out on a sub-page: it hangs off its parent's icon, and a second one would be noise. */
  icon?: IconName;
  current: boolean;
  open?: boolean;
  nested?: boolean;
  /** Set closer: a sidebar with many rows. */
  dense?: boolean;
  trailing?: ReactNode;
  /** How many wait on them here: a small red dot on the icon catches the eye; the number is for screen readers. */
  count?: number;
  /** Set on an area's row: a click opens it in place instead of loading a page (in the rail it stays a link). */
  onToggle?: () => void;
  children: ReactNode;
}) {
  const rail = useContext(RailContext);
  const className = `flex items-center gap-3 rounded-lg px-3 text-sm group-data-[rail=true]/side:justify-center group-data-[rail=true]/side:px-0 ${nested || dense ? "h-8" : "h-9"} ${
    current
      ? "bg-hema-tint font-semibold text-ink"
      : open
        ? "font-semibold text-ink hover:bg-sheet"
        : "text-ink-2 hover:bg-sheet hover:text-ink"
  }`;
  const inside = (
    <>
      {icon && (
        <span className="relative inline-flex shrink-0">
          <Icon name={icon} className={`size-4 ${current ? "text-sage-deep" : open ? "text-ink-2" : "text-ink-3"}`} />
          {count > 0 && (
            <span className="absolute -top-0.5 -right-0.5 size-2 rounded-full bg-danger ring-2 ring-bench">
              <span className="sr-only">{count} waiting on you</span>
            </span>
          )}
        </span>
      )}
      <span className="min-w-0 flex-1 truncate group-data-[rail=true]/side:sr-only">{children}</span>
      {/* A row that leaves says so, the same mark the outside apps carry. */}
      <span className="contents group-data-[rail=true]/side:hidden">{trailing ?? (isAway(href) ? <Icon name="external" className="size-3.5 shrink-0 text-ink-3" /> : null)}</span>
    </>
  );
  if (onToggle && !rail) {
    return (
      <button type="button" onClick={onToggle} aria-expanded={open} className={`w-full text-left ${className}`}>
        {inside}
      </button>
    );
  }
  // Another app is another origin, so there is nothing for Next to route to:
  // it is an ordinary link, and the sign-in it lands on is already held.
  if (isAway(href)) {
    return (
      <a href={href} className={className} title={rail ? String(children) : undefined}>
        {inside}
      </a>
    );
  }
  return (
    <Link href={href} aria-current={current ? "page" : undefined} className={className} title={rail && typeof children === "string" ? children : undefined}>
      {inside}
    </Link>
  );
}

/** A module (or Settings) with pages: one line, opening to its pages while you're inside it. */
function Parent({ href, base, icon, label, groups, overviewHref }: {
  href: string;
  base: string;
  icon: IconName;
  label: string;
  groups: PageGroup[];
  overviewHref?: string;
}) {
  const pathname = usePathname();
  const open = within(pathname, base);
  return (
    <div>
      <Row
        href={href}
        icon={icon}
        current={false}
        open={open}
        trailing={<ChevronRight aria-hidden className={`size-3.5 shrink-0 text-ink-3 transition-transform ${open ? "rotate-90" : ""}`} />}
      >
        {label}
      </Row>
      {open && (
        // The guide line sits under the parent's icon, so the pages read as its own.
        <div className="mt-0.5 mb-1.5 ml-[1.1875rem] animate-reshape space-y-0.5 border-l border-rule pl-2">
          {groups.map((group, i) => (
            <div key={group.label ?? i} role={group.label ? "group" : undefined} aria-label={group.label}>
              {group.label && <p className="px-3 pt-1.5 pb-0.5 text-meta text-ink-3">{group.label}</p>}
              {group.pages.map((page) => (
                <Row key={page.href} href={page.href} icon={page.icon} nested current={isCurrent(page, pathname, page.href === overviewHref)}>
                  {page.label}
                </Row>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** An outside app (the Orders app): opens in its own tab, already signed in. */
function AppLink({ href, icon, label }: { href: string; icon: IconName; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener"
      className="flex h-9 items-center gap-2.5 rounded-lg px-3 text-sm text-ink-2 hover:bg-sheet hover:text-ink"
    >
      <Icon name={icon} className="size-4 text-ink-3" />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <Icon name="external" className="size-3.5 text-ink-3" />
      <span className="sr-only">(opens in a new tab)</span>
    </a>
  );
}

/**
 * A section this app serves, straight in the sidebar.
 *
 * In the shell a section is one line you open, because there are several and
 * only one can be in front of you. A module app has exactly one, and you are
 * already inside it, so a row that opens it would only ever open where you
 * stand. The pages are the section.
 */
function Flat({ groups, overviewHref }: { groups: PageGroup[]; overviewHref?: string }) {
  const pathname = usePathname();
  return (
    <>
      {groups.map((group, i) => (
        <div key={group.label ?? i} role={group.label ? "group" : undefined} aria-label={group.label}>
          {group.label && <p className="px-3 pt-1.5 pb-0.5 text-meta text-ink-3">{group.label}</p>}
          {group.pages.map((page) => (
            <Row
              key={page.href}
              href={page.href}
              icon={page.icon}
              current={isCurrent(page, pathname, page.href === overviewHref)}
            >
              {page.label}
            </Row>
          ))}
        </div>
      ))}
    </>
  );
}

/** One of the other apps: where it is, and what to call it on the way out. */
type Away = { key: string; label: string; icon: IconName; href: string; blank?: boolean };

const PANEL_W = 240;
const EDGE = 8;

/**
 * The other apps, in a panel beside the row that opens it.
 *
 * The sidebar scrolls, so a panel drawn inside it would be cut off at the
 * edge. This one is placed against the viewport from the row's own position,
 * which is also what puts it beside the row on a wide screen and under it on a
 * narrow one.
 */
function AppSwitcher({ items }: { items: Away[] }) {
  const pathname = usePathname();
  const button = useRef<HTMLButtonElement>(null);
  const [at, setAt] = useState<{ top: number; left: number } | null>(null);
  const open = at !== null;

  // The panel belongs to the page it was opened on, so navigating closes it.
  useEffect(() => setAt(null), [pathname]);

  useEffect(() => {
    if (!open) return;
    const shut = () => setAt(null);
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setAt(null);
      button.current?.focus();
    };
    window.addEventListener("resize", shut);
    // Capturing: a scroll in any container moves the row this is pinned to.
    window.addEventListener("scroll", shut, true);
    document.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("resize", shut);
      window.removeEventListener("scroll", shut, true);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function toggle() {
    if (open) return setAt(null);
    const r = button.current?.getBoundingClientRect();
    if (!r) return;
    const beside = window.innerWidth - r.right - EDGE >= PANEL_W;
    // Beside the row when it fits, under it when it does not.
    const left = beside ? r.right + EDGE : Math.min(Math.max(EDGE, r.left), window.innerWidth - PANEL_W - EDGE);
    const wanted = beside ? r.top : r.bottom + EDGE;
    // Enough of it on screen to read, however far down the row sits.
    const height = items.length * 36 + 16;
    setAt({ left, top: Math.max(EDGE, Math.min(wanted, window.innerHeight - height - EDGE)) });
  }

  return (
    <div className="mt-5">
      <button
        ref={button}
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-haspopup="menu"
        className={`flex h-9 w-full items-center gap-2.5 rounded-lg px-3 text-sm ${
          open ? "bg-sheet font-semibold text-ink" : "text-ink-2 hover:bg-sheet hover:text-ink"
        }`}
      >
        <Icon name="apps" className="size-4 text-ink-3" />
        <span className="min-w-0 flex-1 truncate text-left">Other apps</span>
        <ChevronRight aria-hidden className={`size-3.5 shrink-0 text-ink-3 transition-transform ${open ? "rotate-90" : ""}`} />
      </button>
      {at && (
        <>
          {/* Clicking anywhere else puts it away. */}
          <div className="fixed inset-0 z-40" onClick={() => setAt(null)} aria-hidden />
          <div
            role="menu"
            aria-label="Other apps"
            style={{ top: at.top, left: at.left, width: PANEL_W, maxHeight: `calc(100dvh - ${at.top + EDGE}px)` }}
            className="animate-reshape fixed z-50 overflow-y-auto rounded-lg border border-rule bg-bench p-1 shadow-lg"
          >
            {items.map((e) => (
              <a
                key={e.key}
                role="menuitem"
                href={e.href}
                {...(e.blank ? { target: "_blank", rel: "noopener" } : {})}
                className="flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-sm text-ink-2 hover:bg-sheet hover:text-ink"
              >
                <Icon name={e.icon} className="size-4 shrink-0 text-ink-3" />
                <span className="min-w-0 flex-1 truncate">{e.label}</span>
                <Icon name="external" className="size-3.5 shrink-0 text-ink-3" />
                {e.blank && <span className="sr-only">(opens in a new tab)</span>}
              </a>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Group({ label, children, dense = false, first = false }: { label: string; children: ReactNode; dense?: boolean; first?: boolean }) {
  return (
    <div className={`${first ? "" : dense ? "mt-3.5" : "mt-5"} group-data-[rail=true]/side:mt-2`}>
      <p className={`px-3 text-ink-3 uppercase group-data-[rail=true]/side:sr-only ${dense ? "mb-0.5 text-[0.625rem] leading-4 font-semibold tracking-[0.08em]" : "mb-1 text-caps"}`}>{label}</p>
      {!first && <hr className="mx-3 mb-2 hidden border-rule group-data-[rail=true]/side:block" aria-hidden />}
      <div className={dense ? "space-y-px" : "space-y-0.5"}>{children}</div>
    </div>
  );
}

/**
 * Whether this app serves a department's pages itself.
 *
 * Its pages are mounted under `/m/<key>`, which is the shell's shape, so only
 * the shell — or the module's own app — can open them. A module with no app of
 * its own is the shell's alone.
 */
function serves(m: ModuleAccess): boolean {
  const app = appOf(m.key);
  return !THIS_APP || (app !== null && THIS_APP === app);
}

function ModuleEntry({ m }: { m: ModuleAccess }) {
  const root = moduleBase(m.key) || "/";
  return <Parent href={root} base={root} icon={moduleIcon(m.key)} label={m.name} groups={[{ pages: modulePages(m) }]} overviewHref={root} />;
}

function Links({ me }: { me: Me }) {
  const pathname = usePathname();
  // On the platform there is no company, so there is nothing of one to list:
  // only the companies themselves, until one is opened.
  if (me.org === null) {
    const companies = platformHome();
    return (
      <nav aria-label="Main">
        <Row href={companies} icon="companies" current={!isAway(companies) && within(pathname, companies)}>
          Companies
        </Row>
      </nav>
    );
  }
  const crm = me.modules.filter((m) => m.kind === "crm");
  // Only modules with screens: every link here is a choice, and "Soon" isn't one anyone can take.
  const departments = me.modules.filter((m) => m.kind === "department" && m.built);
  // Apps with their own screens, once they're live.
  const apps = me.modules.filter((m) => m.kind === "app" && m.url);
  // A Developer Admin reaches some of Settings and none of the rest, so the
  // section appears when there is at least one page in it for them.
  const settings = settingsFor(me);

  // Each app draws the sections it serves and nothing else. Every other app is
  // one row, because from here that is all it is: an address. Analytics is an
  // app like the rest — the dashboard is its screen, not a page of this one —
  // so it goes in the same list rather than sitting at the top pretending to
  // belong here. The shell serves them all, so only the outside apps are away
  // in it and it reads exactly as it did before.
  const elsewhere: Away[] = [];
  if (!isOurs("exec")) {
    elsewhere.push({ key: "exec", label: appLabel("exec"), icon: "reports", href: appUrl("exec") });
  }
  if (crm.length > 0 && !isOurs("crm")) {
    elsewhere.push({ key: "crm", label: appLabel("crm"), icon: moduleIcon("crm"), href: appUrl("crm") });
  }
  for (const m of departments) {
    const app = appOf(m.key);
    // A department with no app of its own has nowhere to be sent, so from
    // another app it is left out rather than linked into a page that isn't there.
    if (app && !isOurs(app)) elsewhere.push({ key: m.key, label: m.name, icon: moduleIcon(m.key), href: appUrl(app) });
  }
  // The outside apps carry their own address from the API, so they are away
  // from everywhere, the shell included.
  for (const m of apps) elsewhere.push({ key: m.key, label: m.name, icon: moduleIcon(m.key), href: m.url!, blank: true });
  if (settings.length > 0 && !isOurs("exec")) {
    elsewhere.push({ key: "exec", label: appLabel("exec"), icon: "settings", href: settings[0].pages[0].href });
  }
  // The companies list is Platform's screen. In the shell it sits inside
  // Settings, where it has always been; anywhere else Platform is just another
  // app, and a row of its own is what it is.
  if (THIS_APP && !isOurs("platform") && develops(me)) {
    elsewhere.push({ key: "platform", label: appLabel("platform"), icon: "companies", href: appUrl("platform") });
  }

  return (
    <nav aria-label="Main">
      {/* The dashboard is Analytics' screen, so the row is Analytics' own app's
          and the shell's. Everywhere else Analytics is a link like any app. */}
      {isOurs("exec") &&
        (THIS_APP ? (
          // In its own app Analytics is a section like any other, with a
          // heading of its own. The dashboard is its screen, not this app's
          // front door, and the sidebar should not say otherwise.
          <Group label={appLabel("exec")}>
            <Row href="/" icon="home" current={pathname === "/"}>
              Home
            </Row>
          </Group>
        ) : (
          // The shell's own front door, which is every app at once.
          <Row href="/" icon="home" current={pathname === "/"}>
            Home
          </Row>
        ))}
      {/* Platform's one screen, in Platform's own app. In the shell it is a
          page of Settings instead, which is where it has always been. */}
      {THIS_APP === "platform" && develops(me) && (
        <Group label={appLabel("platform")}>
          <Row href="/" icon="companies" current={pathname === "/"}>
            Companies
          </Row>
        </Group>
      )}
      {/* The CRM, as one set of pages. No division rows under it:
          a division is a property of a record, not a place, so these are the
          same pages whether you sell in one of the seven or all of them. */}
      {crm.length > 0 && isOurs("crm") && (
        <Group label={appLabel("crm")}>
          {crmPages(me).map((page) => (
            <Row key={page.href} href={page.href} icon={page.icon} current={isCurrent(page, pathname, false)}>
              {page.label}
            </Row>
          ))}
        </Group>
      )}
      {/* The CRM's own Administration: its users, roles, teams and audit log,
          each page only for a role that may open it. */}
      {THIS_APP === "crm" && adminPagesFor(me).length > 0 && (
        <Group label="Administration">
          {adminPagesFor(me).map((page) => (
            <Row key={page.href} href={page.href} icon={page.icon} current={within(pathname, page.href) || page.also.some((a) => within(pathname, a))}>
              {page.label}
            </Row>
          ))}
        </Group>
      )}
      {THIS_APP !== "inventory" && departments.some(serves) && (
        <Group label={THIS_APP ? (departments.find(serves)?.name ?? "Departments") : "Departments"}>
          {departments.filter(serves).map((m) =>
            THIS_APP ? (
              <Flat key={m.key} groups={[{ pages: modulePages(m) }]} overviewHref={moduleBase(m.key) || "/"} />
            ) : (
              <ModuleEntry key={m.key} m={m} />
            ),
          )}
        </Group>
      )}
      {/* The apps this person has but is not in. The shell keeps them as the
          plain list they have always been, in the slot they have always had;
          a module app has more of them, so there they fold into one row that
          opens beside itself. */}
      {SHOW_OTHER_APPS &&
        elsewhere.length > 0 &&
        (THIS_APP ? (
          <AppSwitcher items={elsewhere} />
        ) : (
          <Group label="Apps">
            {elsewhere.map((e) =>
              e.blank ? (
                <AppLink key={e.key} href={e.href} icon={e.icon} label={e.label} />
              ) : (
                <Row key={e.key} href={e.href} icon={e.icon} current={false}>
                  {e.label}
                </Row>
              ),
            )}
          </Group>
        ))}
      {settings.length > 0 && isOurs("exec") && (
        <Group label={appLabel("exec")}>
          {THIS_APP ? (
            /* Its own overview first, the way every other app opens on one.
               Only in the Admin app: in the shell "/" is the shell's own
               dashboard, which is Analytics' screen and nothing to do with
               Settings. */
            <Flat
              groups={[{ pages: [{ href: "/", label: "Overview", icon: "overview" }] }, ...settings]}
              overviewHref="/"
            />
          ) : (
            /* Opens on the first page this person reaches, which is People for
               an Admin and for a Developer Admin alike. */
            <Parent
              href={settings[0].pages[0].href}
              base="/settings"
              icon="settings"
              label="Settings"
              groups={settings}
            />
          )}
        </Group>
      )}
    </nav>
  );
}

/** Where you are, in words, for the phone's top bar (the sidebar shows it on wider screens). */
function placeOf(pathname: string, search: URLSearchParams, me: Me): string | null {
  if (THIS_APP === "inventory") {
    const { home, sections } = inventoryNav(me);
    if (home && (pathname === "/" || within(pathname, "/alerts"))) return home.label;
    const place = currentPlace(placesOf(sections), pathname, search);
    const area = sections.flatMap((x) => x.areas).find((a) => a.places.length > 1 && place !== undefined && a.places.includes(place));
    return place ? (area ? `${area.label} · ${place.label}` : place.label) : null;
  }
  if (THIS_APP === "crm" && within(pathname, "/admin")) {
    const page = adminPagesFor(me).find((p) => within(pathname, p.href) || p.also.some((a) => within(pathname, a)));
    return page ? `Administration · ${page.label}` : "Administration";
  }
  if (within(pathname, "/settings")) {
    const page = settingsFor(me).flatMap((g) => g.pages).find((p) => !isAway(p.href) && within(pathname, p.href));
    return page ? `Settings · ${page.label}` : "Settings";
  }
  // In a module's own app every path below it is that module's; in the shell
  // it is whichever module's mount the path sits under.
  const m = THIS_APP
    ? me.modules.find((x) => appOf(x.key) === THIS_APP)
    : me.modules.find((x) => within(pathname, `/m/${x.key}`));
  if (m) {
    const root = moduleBase(m.key) || "/";
    const page = modulePages(m).find((p) => isCurrent(p, pathname, p.href === root));
    return page && page.href !== root ? `${m.name} · ${page.label}` : m.name;
  }
  return crmPages(me).find((p) => isCurrent(p, pathname, false))?.label ?? null;
}

/** `actions`: the bell and the profile, which sit at the top right; on a phone, beside the menu button. */
export function Nav({ me, waiting = {}, unset = {}, rail: railAtFirst = false, actions }: { me: Me; waiting?: Waiting; unset?: Unset; rail?: boolean; actions?: ReactNode }) {
  const pathname = usePathname();
  const [rail, setRail] = useState(railAtFirst);
  function toggleRail() {
    const next = !rail;
    setRail(next);
    // A cookie, so the next page is drawn the same way from the start.
    document.cookie = `bishnoi_nav=${next ? "rail" : "full"}; path=/; max-age=31536000; samesite=lax`;
  }
  // The phone menu belongs to the page it was opened on, so navigating closes it.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = openOn === pathname;
  const search = useSearchParams();
  const place = placeOf(pathname, search, me);

  const brand = (
    <Link href="/" className="flex items-center gap-2.5 border-b border-rule pb-4">
      <img src="/brand/bishnoi-one-mark.png" alt="" width={36} height={36} className="size-9 shrink-0" />
      <span className="min-w-0">
        {/* Which app this is, not only which product. Each one is its own site on
            its own address, so "Bishnoi One" alone leaves you working out from the port
            whether the screen in front of you is missing or simply elsewhere. */}
        <span className="block truncate text-sm leading-tight font-semibold text-ink">
          {thisAppLabel() ? `${APP_NAME} ${thisAppLabel()}` : APP_NAME}
        </span>
        {/* No company on the platform: a Developer Admin has not opened one, and
            saying a company name there would be saying something untrue. */}
        <span className="block truncate text-meta text-ink-3">{me.org?.brandName ?? "Platform"}</span>
      </span>
    </Link>
  );

  return (
    <>
      {/* Desktop: a fixed column on the bench. */}
      <aside data-rail={rail} className="group/side sticky top-0 hidden h-dvh w-[16.5rem] flex-col justify-between overflow-x-hidden overflow-y-auto px-4 py-6 transition-[width] duration-200 data-[rail=true]:w-[4.75rem] data-[rail=true]:px-2.5 lg:flex">
        <RailContext.Provider value={rail}>
          <div>
            <div className={`${THIS_APP === "inventory" ? "mb-4" : "mb-6"} flex items-start gap-1 px-3 group-data-[rail=true]/side:flex-col group-data-[rail=true]/side:items-center group-data-[rail=true]/side:px-0`}>
              <div className="min-w-0 flex-1 group-data-[rail=true]/side:[&_span]:sr-only group-data-[rail=true]/side:[&_a]:border-b-0 group-data-[rail=true]/side:[&_a]:pb-0">{brand}</div>
              <button
                type="button"
                onClick={toggleRail}
                aria-label={rail ? "Open the sidebar" : "Close the sidebar"}
                title={rail ? "Open the sidebar" : "Close the sidebar"}
                className="grid size-8 shrink-0 place-items-center rounded-lg text-ink-3 hover:bg-sheet hover:text-ink group-data-[rail=true]/side:mt-3"
              >
                {rail ? <PanelLeftOpen className="size-4" aria-hidden /> : <PanelLeftClose className="size-4" aria-hidden />}
              </button>
            </div>
            {THIS_APP === "inventory" ? <InventoryLinks me={me} waiting={waiting} unset={unset} /> : <Links me={me} />}
          </div>
        </RailContext.Provider>
      </aside>

      {/* Phone and tablet: a top bar with a menu, saying where you are. */}
      <div className="sticky top-0 z-30 bg-bench/95 backdrop-blur lg:hidden">
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <div className="w-36 shrink-0">{brand}</div>
          <div className="flex min-w-0 items-center gap-1">
            {actions}
            <button
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
          <div id="phone-menu" className="animate-reshape max-h-[calc(100dvh-4.5rem)] overflow-y-auto border-t border-rule px-3 pt-3 pb-5">
            {THIS_APP === "inventory" ? <InventoryLinks me={me} waiting={waiting} unset={unset} /> : <Links me={me} />}
          </div>
        )}
      </div>
    </>
  );
}
