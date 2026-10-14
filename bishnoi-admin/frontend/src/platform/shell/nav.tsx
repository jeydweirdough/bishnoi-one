"use client";

import { ChevronRight, LogOut, Menu, MoreHorizontal, PanelLeftClose, PanelLeftOpen, UserRound, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Avatar } from "../ui/avatar";
import { ConfirmButton } from "../ui/confirm";
import { Icon, moduleIcon, type IconName } from "../ui/icons";
import { signOut } from "../actions/session";
import { THIS_APP, appLabel, appOf, appUrl, href as appHref, isOurs, moduleBase, platformHome, thisAppLabel } from "../lib/apps";
import { APP_NAME } from "../lib/labels";
import type { Me, ModuleAccess } from "../lib/types";

// The one place everyone finds their way.
//
// A sales division is not a section of the app: Overview, Customers, Follow-ups
// and Retention are the same pages whichever division a record is in, and their
// contents merge. So they are five plain links, the same for someone in one
// division as for someone in six.
//
// A department is different. Inventory's pages (products, promos, bundles) are
// nothing like Finance's (approvals, letters, payments), so a department really
// is a section, and opens to show its own.

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
  /** What isn't set up yet there. */
  missing?: Missing;
};
type PageGroup = { label?: string; pages: Page[] };

/** How many things aren't set up yet, by kind (the API's /admin/unset). */
export type Unset = Record<string, number>;

type Missing = { count: number; says: string };

/** What each kind's red mark says when pointed at. */
const UNSET_SAYS: Record<string, (n: number) => string> = {
  propertyRent: (n) => `${n} ${n === 1 ? "property has" : "properties have"} no monthly rent`,
  documentExpiry: (n) => `${n} ${n === 1 ? "document has" : "documents have"} no expiry date, so no renewal alert can be sent`,
};

/** What isn't set of these kinds: how many, and what to say about it. */
function missingOf(unset: Unset, keys: string[]): Missing {
  const found = keys.filter((key) => unset[key]);
  return { count: found.reduce((n, key) => n + unset[key], 0), says: found.map((key) => UNSET_SAYS[key](unset[key])).join(". ") };
}

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

/** The sales workspace: one set of pages over every division a person sells in. */
function crmPages(sales: ModuleAccess[]): Page[] {
  return [
    // The Sales app opens on its overview; in the shell that screen is a page
    // of its own, because the shell's own root is the dashboard.
    { href: THIS_APP === "crm" ? "/" : "/overview", label: "Overview", icon: "overview" },
    // A quote is opened from its customer, so it counts as being in Customers.
    { href: "/customers", label: "Customers", icon: "customers", also: ["/quotes"] },
    { href: "/follow-ups", label: "Follow-ups", icon: "followUps" },
    { href: "/retention", label: "Retention", icon: "retention" },
    // Only the leads who set what a team charges; a rep quoting from those
    // prices has no use for the page.
    ...(sales.some((m) => m.actions.includes("prices")) ? [{ href: "/prices", label: "Prices", icon: "pricing" as const }] : []),
  ];
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
  if (m.key === "inventory") {
    return [
      { href: root, label: "Overview", icon: "overview" },
      { href: `${base}/products`, label: "Products and prices", icon: "products" },
      { href: `${base}/promos`, label: "Promos and discounts", icon: "promos" },
      // Beside promos, because a person looks for both in the same place.
      { href: `${base}/bundles`, label: "Bundles", icon: "bundles" },
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
  trailing,
  children,
}: {
  href: string;
  icon: IconName;
  current: boolean;
  open?: boolean;
  nested?: boolean;
  trailing?: ReactNode;
  children: ReactNode;
}) {
  const rail = useContext(RailContext);
  const className = `flex items-center gap-2.5 rounded-full px-3 text-sm group-data-[rail=true]/side:justify-center group-data-[rail=true]/side:px-0 ${nested ? "h-8" : "h-9"} ${
    current
      ? "bg-hema-tint font-semibold text-ink"
      : open
        ? "font-semibold text-ink hover:bg-sheet"
        : "text-ink-2 hover:bg-sheet hover:text-ink"
  }`;
  const inside = (
    <>
      <Icon name={icon} className={`size-4 ${current ? "text-sage-deep" : open ? "text-ink-2" : "text-ink-3"}`} />
      <span className="min-w-0 flex-1 truncate group-data-[rail=true]/side:sr-only">{children}</span>
      {/* A row that leaves says so, the same mark the outside apps carry. */}
      <span className="contents group-data-[rail=true]/side:hidden">{trailing ?? (isAway(href) ? <Icon name="external" className="size-3.5 shrink-0 text-ink-3" /> : null)}</span>
    </>
  );
  // Another app is another origin, so there is nothing for Next to route to:
  // it is an ordinary link, and the sign-in it lands on is already held.
  if (isAway(href)) {
    return (
      <a href={href} className={className} title={rail && typeof children === "string" ? children : undefined}>
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
        <div className="mt-0.5 mb-1.5 ml-[1.1875rem] animate-reshape space-y-0.5 border-l border-rule pl-2 group-data-[rail=true]/side:hidden">
          {groups.map((group, i) => (
            <div key={group.label ?? i} role={group.label ? "group" : undefined} aria-label={group.label}>
              {group.label && <p className="px-3 pt-1.5 pb-0.5 text-meta text-ink-3 group-data-[rail=true]/side:sr-only">{group.label}</p>}
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
      title={label}
      className="flex h-9 items-center gap-2.5 rounded-[12px] px-3 text-sm text-ink hover:bg-bench group-data-[rail=true]/side:justify-center group-data-[rail=true]/side:px-0"
    >
      <Icon name={icon} className="size-4 shrink-0 text-ink" />
      <span className="min-w-0 flex-1 truncate group-data-[rail=true]/side:sr-only">{label}</span>
      <Icon name="external" className="size-3.5 text-ink-3 group-data-[rail=true]/side:hidden" />
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
          {group.label && <p className="px-3 pt-1.5 pb-0.5 text-meta text-ink-3 group-data-[rail=true]/side:sr-only">{group.label}</p>}
          {group.pages.map((page) => (
            <Row
              key={page.href}
              href={page.href}
              icon={page.icon}
              current={isCurrent(page, pathname, page.href === overviewHref)}
              trailing={page.missing?.count ? <UnsetMark missing={page.missing} /> : undefined}
            >
              {page.label}
            </Row>
          ))}
        </div>
      ))}
    </>
  );
}

/**
 * How many things there aren't set up yet: red, because until they are
 * something doesn't work (a document with no expiry date never raises an alert).
 */
function UnsetMark({ missing }: { missing: Missing }) {
  return (
    <span title={missing.says} className="ml-auto inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-danger px-1.5 text-[0.6875rem] font-semibold text-white tabular-nums">
      {missing.count}
      <span className="sr-only"> not set yet: {missing.says}</span>
    </span>
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
        title="Other apps"
        className={`flex h-9 w-full items-center gap-2.5 rounded-[12px] px-3 text-sm group-data-[rail=true]/side:justify-center group-data-[rail=true]/side:px-0 ${
          open ? "bg-bench font-semibold text-ink" : "text-ink hover:bg-bench"
        }`}
      >
        <Icon name="apps" className="size-4 shrink-0 text-ink" />
        <span className="min-w-0 flex-1 truncate text-left group-data-[rail=true]/side:sr-only">Other apps</span>
        <ChevronRight aria-hidden className={`size-3.5 shrink-0 text-ink-3 transition-transform group-data-[rail=true]/side:hidden ${open ? "rotate-90" : ""}`} />
      </button>
      {at && (
        <>
          {/* Clicking anywhere else puts it away. */}
          <div className="fixed inset-0 z-40" onClick={() => setAt(null)} aria-hidden />
          <div
            role="menu"
            aria-label="Other apps"
            style={{ top: at.top, left: at.left, width: PANEL_W, maxHeight: `calc(100dvh - ${at.top + EDGE}px)` }}
            className="animate-reshape fixed z-50 overflow-y-auto rounded-[12px] border border-rule bg-bench p-1 shadow-lg"
          >
            {items.map((e) => (
              <a
                key={e.key}
                role="menuitem"
                href={e.href}
                {...(e.blank ? { target: "_blank", rel: "noopener" } : {})}
                className="flex h-9 items-center gap-2.5 rounded-[12px] px-2.5 text-sm text-ink-2 hover:bg-sheet hover:text-ink"
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

function Group({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="mt-5 group-data-[rail=true]/side:mt-2">
      <p className="mb-1 px-3 text-caps text-ink-3 uppercase group-data-[rail=true]/side:sr-only">{label}</p>
      <hr className="mx-3 mb-2 hidden border-rule group-data-[rail=true]/side:block" aria-hidden />
      <div className="space-y-0.5">{children}</div>
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

/** The executive pages this person's role sees, with what isn't set up yet on each. */
const executivePages = (me: Me, unset: Unset, pages: Page[] = EXECUTIVE_PAGES): Page[] =>
  pages.filter((p) => !p.reach || p.reach(me)).map((p) =>
    p.href === "/documents" ? { ...p, missing: missingOf(unset, ["documentExpiry"]) } : p.href === "/properties" ? { ...p, missing: missingOf(unset, ["propertyRent"]) } : p,
  );

/** A role that holds this permission reaches the page (the API checks the same). */
const sees = (permission: string) => (me: Me) => me.permissions?.includes(permission) ?? me.canManageSettings;

const EXECUTIVE_PAGES: Page[] = [
  { href: "/", label: "Home", icon: "home", reach: sees("dashboard.view") },
  { href: "/notifications", label: "Renewal alerts", icon: "notifications", reach: sees("notifications.view") },
];

/** The CRM's kind of menu: headed sections, each the work it holds. */
const COMPLIANCE_PAGES: Page[] = [
  { href: "/permits", label: "Permits", icon: "permits", reach: sees("permits.view") },
  { href: "/immigration", label: "Expatriates", icon: "immigration", reach: sees("immigration.view") },
  { href: "/documents", label: "Documents", icon: "documents", reach: sees("documents.view") },
  { href: "/properties", label: "Properties", icon: "properties", reach: sees("properties.view") },
];
const OFFICE_PAGES: Page[] = [{ href: "/tickets", label: "Office requests", icon: "tickets", reach: sees("tickets.view") }];

/** The executive assistant's trackers, under their own heading. */
const FLEET_PAGES: Page[] = [
  { href: "/vehicles", label: "Vehicles", icon: "vehicles", reach: sees("vehicles.view") },
  { href: "/fuel-cards", label: "Fuel cards", icon: "fuelCards", reach: sees("vehicles.view") },
  { href: "/travel", label: "Hotel and flights", icon: "travel", reach: sees("travel.view") },
  { href: "/devices", label: "Devices issued", icon: "devices", reach: sees("devices.view") },
];
const fleetPages = (me: Me): Page[] => FLEET_PAGES.filter((p) => !p.reach || p.reach(me));

function adminPagesFor(me: Me): Page[] {
  const may = (permission: string) => me.permissions?.includes(permission) ?? me.canManageSettings;
  return [
    ...(may("admin.users")
      ? [{ href: "/admin/users", label: "Users", icon: "people" as const, also: ["/admin/users"] }]
      : []),
    ...(may("admin.roles")
      ? [{ href: "/admin/roles", label: "Roles and permissions", icon: "roles" as const, also: ["/admin/roles"] }]
      : []),
    ...(may("admin.audit")
      ? [{ href: "/admin/audit", label: "Activity log", icon: "auditLog" as const, also: ["/admin/audit"] }]
      : []),
  ];
}

function Links({ me, unset }: { me: Me; unset: Unset }) {

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
      {/* Platform's one screen, in Platform's own app. */}
      {THIS_APP === "platform" && develops(me) && (
        <Group label={appLabel("platform")}>
          <Row href="/" icon="companies" current={pathname === "/"}>
            Companies
          </Row>
        </Group>
      )}
      {/* Executive Admin's primary operational workspace */}
      {isOurs("exec") && (
        <>
          <div className="mt-2">
            <Flat groups={[{ pages: executivePages(me, unset) }]} overviewHref="/" />
          </div>
          {(
            [
              ["Compliance", executivePages(me, unset, COMPLIANCE_PAGES)],
              ["Fleet and travel", fleetPages(me)],
              ["Office", executivePages(me, unset, OFFICE_PAGES)],
            ] as [string, Page[]][]
          ).map(
            ([label, pages]) =>
              pages.length > 0 && (
                <Group key={label} label={label}>
                  <Flat groups={[{ pages }]} />
                </Group>
              ),
          )}
        </>
      )}
      {/* The CRM, as one set of pages. */}
      {crm.length > 0 && isOurs("crm") && (
        <Group label={appLabel("crm")}>
          {crmPages(crm).map((page) => (
            <Row key={page.href} href={page.href} icon={page.icon} current={isCurrent(page, pathname, false)}>
              {page.label}
            </Row>
          ))}
        </Group>
      )}
      {/* Executive Admin's own module is the group above, so it isn't listed again. */}
      {departments.some(serves) && THIS_APP !== "exec" && (
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
      {/* Administration (Users, Roles & Permissions, Activity log) */}
      {adminPagesFor(me).length > 0 && isOurs("exec") && (
        <Group label="Administration">
          {adminPagesFor(me).map((page) => (
            <Row
              key={page.href}
              href={page.href}
              icon={page.icon}
              current={within(pathname, page.href) || (page.also ?? []).some((a) => within(pathname, a))}
            >
              {page.label}
            </Row>
          ))}
        </Group>
      )}
    </nav>
  );
}

/** Where you are, in words, for the phone's top bar (the sidebar shows it on wider screens). */
function placeOf(pathname: string, me: Me): string | null {
  if (within(pathname, "/admin")) {
    const page = adminPagesFor(me).find(
      (p) => within(pathname, p.href) || (p.also ?? []).some((a) => within(pathname, a)),
    );
    return page ? `Administration · ${page.label}` : "Administration";
  }
  if (within(pathname, "/settings")) {
    return "Administration";
  }
  const execPage = EXECUTIVE_PAGES.find((p) => isCurrent(p, pathname, p.href === "/"));
  if (execPage) {
    return `Bishnoi One Admin · ${execPage.label}`;
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
  const crm = me.modules.filter((x) => x.kind === "crm");
  return crmPages(crm).find((p) => isCurrent(p, pathname, false))?.label ?? null;
}

function Account({ me }: { me: Me }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const menu = useRef<HTMLDivElement>(null);
  // Closes on a click elsewhere or Escape, as a menu does.
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => menu.current && !menu.current.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  const here = pathname === "/account" || pathname.startsWith("/account/");
  // The CRM's foot (without Ant Design): who you are, and the rest behind ⋯.
  return (
    <div className="border-t border-rule pt-4">
      <div ref={menu} className={`relative flex items-center gap-1 rounded-full pr-1 group-data-[rail=true]/side:flex-col group-data-[rail=true]/side:pr-0 ${here ? "bg-hema-tint" : ""}`}>
        <Link href="/account" aria-current={pathname === "/account" ? "page" : undefined} className={`flex min-w-0 flex-1 items-center gap-2.5 rounded-full px-3 py-1.5 group-data-[rail=true]/side:px-1.5 ${here ? "" : "hover:bg-sheet"}`} title={me.user.fullName}>
          <Avatar name={me.user.fullName} id={me.user.id} photoAt={me.user.photoAt} size="md" />
          <span className="min-w-0 group-data-[rail=true]/side:sr-only">
            <span className="block truncate text-sm font-semibold text-ink">{me.user.fullName}</span>
            <span className="block truncate text-meta text-ink-3">{me.user.email}</span>
          </span>
        </Link>
        <button
          type="button"
          aria-label="Account options"
          title="Account options"
          aria-expanded={open}
          aria-haspopup="menu"
          onClick={() => setOpen((o) => !o)}
          className="grid size-9 shrink-0 place-items-center rounded-full text-ink-3 transition-colors hover:bg-sheet hover:text-ink focus-visible:text-ink"
        >
          <MoreHorizontal className="size-5" aria-hidden />
        </button>
        {open && (
          <div role="menu" className="absolute right-0 bottom-full z-40 mb-2 w-52 group-data-[rail=true]/side:right-auto group-data-[rail=true]/side:left-0 rounded-[16px] border border-rule bg-sheet p-1.5 shadow-overlay">
            <Link role="menuitem" href="/account" onClick={() => setOpen(false)} className="flex items-center gap-2.5 rounded-[10px] px-3 py-2 text-sm text-ink hover:bg-mint">
              <UserRound className="size-4" aria-hidden />
              Your account
            </Link>
            <div className="my-1 border-t border-rule" />
            <ConfirmButton
              label="Sign out"
              icon={<LogOut className="size-4" aria-hidden />}
              triggerVariant="quiet"
              triggerSize="sm"
              triggerClassName="w-full !justify-start !rounded-[10px] !px-3 !text-ink !font-normal"
              title="Sign out?"
              body="You'll need your email and password to get back in."
              confirmLabel="Sign out"
              danger={false}
              onConfirm={async () => {
                await signOut();
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export function Nav({ me, unset = {}, rail: railAtFirst = false }: { me: Me; unset?: Unset; rail?: boolean }) {
  const pathname = usePathname();
  const [rail, setRail] = useState(railAtFirst);
  function toggleRail() {
    const next = !rail;
    setRail(next);
    // A cookie, so the next page is drawn the same way from the start; every app reads the same one.
    document.cookie = `bishnoi_nav=${next ? "rail" : "full"}; path=/; max-age=31536000; samesite=lax`;
  }
  // The phone menu belongs to the page it was opened on, so navigating closes it.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = openOn === pathname;
  const place = placeOf(pathname, me);

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
      {/* Desktop: a light grey column beside the page, a rule between them. */}
      <aside data-rail={rail} className="group/side sticky top-0 hidden h-dvh w-[16.5rem] flex-col justify-between overflow-x-hidden overflow-y-auto px-4 py-6 transition-[width] duration-200 data-[rail=true]:w-[4.75rem] data-[rail=true]:px-2.5 lg:flex">
        <RailContext.Provider value={rail}>
          <div>
            <div className="mb-6 flex items-start gap-1 px-3 group-data-[rail=true]/side:flex-col group-data-[rail=true]/side:items-center group-data-[rail=true]/side:px-0">
              <div className="min-w-0 flex-1 group-data-[rail=true]/side:[&_span]:sr-only group-data-[rail=true]/side:[&_a]:border-b-0 group-data-[rail=true]/side:[&_a]:pb-0">{brand}</div>
              <button
                type="button"
                onClick={toggleRail}
                aria-label={rail ? "Open the sidebar" : "Close the sidebar"}
                title={rail ? "Open the sidebar" : "Close the sidebar"}
                className="grid size-8 shrink-0 place-items-center rounded-full text-ink-3 hover:bg-sheet hover:text-ink group-data-[rail=true]/side:mt-3"
              >
                {rail ? <PanelLeftOpen className="size-4" aria-hidden /> : <PanelLeftClose className="size-4" aria-hidden />}
              </button>
            </div>
            <Links me={me} unset={unset} />
          </div>
          <Account me={me} />
        </RailContext.Provider>
      </aside>

      {/* Phone and tablet: a top bar with a menu, saying where you are. */}
      <div className="sticky top-0 z-30 bg-bench/95 backdrop-blur lg:hidden">
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <div className="w-36 shrink-0">{brand}</div>
          <button
            type="button"
            onClick={() => setOpenOn(open ? null : pathname)}
            aria-expanded={open}
            aria-controls="phone-menu"
            className="inline-flex h-10 min-w-0 items-center gap-2 rounded-full pr-2 pl-3 text-ink hover:bg-sheet"
          >
            {place && <span className="min-w-0 truncate text-meta font-semibold text-ink-2">{place}</span>}
            {open ? <X className="size-5 shrink-0" aria-hidden /> : <Menu className="size-5 shrink-0" aria-hidden />}
            <span className="sr-only">{open ? "Close menu" : "Open menu"}</span>
          </button>
        </div>
        {open && (
          <div id="phone-menu" className="animate-reshape max-h-[calc(100dvh-4.5rem)] overflow-y-auto border-t border-rule px-3 pt-3 pb-5">
            <Links me={me} unset={unset} />
            <div className="mt-5">
              <Account me={me} />
            </div>
          </div>
        )}
      </div>
    </>
  );
}
