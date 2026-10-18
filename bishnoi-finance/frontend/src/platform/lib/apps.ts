/**
 * Where each Bishnoi One app lives.
 *
 * Every module runs as its own app on its own address, so a link from one to
 * another is not a path — it is a whole URL. This is the one place that knows
 * which app owns which screen.
 *
 * Addresses come from Bishnoi One Platform (Applications), read as each page is
 * served (lib/addresses.ts): a new domain is set there once. Before it answers,
 * NEXT_PUBLIC_ settings if any, then the local ports, so `npm run dev` just works.
 */

import type { Me } from "./types";

/**
 * The seven Bishnoi One apps are the company's own modules, one each, as the API
 * lists them in app/modules.py — Executive Admin, Finance, In-Licensing,
 * Inventory, Pharmacy, Regulatory, and the CRM over the seven sales divisions.
 *
 * Admin and Platform are not modules and never appear in that seven: Admin is
 * the company's own controls, and Platform sits above every company at once.
 * They are apps all the same, so they live here with the rest.
 *
 * Keys match the API's module keys, so a module key is an app name already.
 */
export type AppName =
  | "exec"
  | "crm"
  | "finance"
  | "inventory"
  | "regulatory"
  | "inlicensing"
  | "pharmacy"
  | "platform";

const DEFAULTS: Record<AppName, string> = {
  exec: "http://localhost:4300",
  crm: "http://localhost:4302",
  finance: "http://localhost:4303",
  inventory: "http://localhost:4304",
  platform: "http://localhost:4305",
  inlicensing: "http://localhost:4306",
  pharmacy: "http://localhost:4307",
  regulatory: "http://localhost:4308",
};

const FROM_ENV: Record<AppName, string | undefined> = {
  exec: (process.env.NEXT_PUBLIC_BISHNOI_EXEC_URL ?? process.env.NEXT_PUBLIC_NABHI_EXEC_URL),
  crm: (process.env.NEXT_PUBLIC_BISHNOI_CRM_URL ?? process.env.NEXT_PUBLIC_NABHI_CRM_URL),
  finance: (process.env.NEXT_PUBLIC_BISHNOI_FINANCE_URL ?? process.env.NEXT_PUBLIC_NABHI_FINANCE_URL),
  inventory: (process.env.NEXT_PUBLIC_BISHNOI_INVENTORY_URL ?? process.env.NEXT_PUBLIC_NABHI_INVENTORY_URL),
  platform: (process.env.NEXT_PUBLIC_BISHNOI_PLATFORM_URL ?? process.env.NEXT_PUBLIC_NABHI_PLATFORM_URL),
  inlicensing: (process.env.NEXT_PUBLIC_BISHNOI_INLICENSING_URL ?? process.env.NEXT_PUBLIC_NABHI_INLICENSING_URL),
  pharmacy: (process.env.NEXT_PUBLIC_BISHNOI_PHARMACY_URL ?? process.env.NEXT_PUBLIC_NABHI_PHARMACY_URL),
  regulatory: (process.env.NEXT_PUBLIC_BISHNOI_REGULATORY_URL ?? process.env.NEXT_PUBLIC_NABHI_REGULATORY_URL),
};

/** Which app this one is. Each app sets it; unset means the shell, which has them all. */
export const THIS_APP = ((process.env.NEXT_PUBLIC_BISHNOI_APP ?? process.env.NEXT_PUBLIC_NABHI_APP) ?? "") as AppName | "";

// What the Platform says (lib/addresses.ts), set as each page is served.
let LIVE: Partial<Record<AppName, string>> = {};

export function setAddresses(map: Partial<Record<AppName, string>>): void {
  LIVE = map;
}

/** Where an app's screens are: as the Platform's Applications page says; else NEXT_PUBLIC_, else the local port. */
export const appUrl = (app: AppName): string => (LIVE[app] || FROM_ENV[app] || DEFAULTS[app]).replace(/\/$/, "");

/** Whether an app's address is known for real (the Platform says, or it's set), not only the local default. */
export const addressKnown = (app: AppName): boolean => Boolean(LIVE[app] || FROM_ENV[app]);

/**
 * A link to a screen, wherever it lives.
 *
 * Within the app you are already in it stays a path, so Next routes it without
 * a page load. Anywhere else it becomes the other app's full address.
 */
export function href(app: AppName, path: string): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  if (!THIS_APP || THIS_APP === app) return clean;
  return `${appUrl(app)}${clean}`;
}

/** True when this link leaves for another app, so the sidebar can say so. */
export const leaves = (app: AppName): boolean => Boolean(THIS_APP) && THIS_APP !== app;

const NAMES = new Set<string>(Object.keys(DEFAULTS));

/**
 * The app that owns a module's screens, by its key — `finance` is
 * `bishnoi-finance`'s. Null when no app of ours has them, which is every module
 * that only ever lived in the shell, and the outside apps (Orders) that carry
 * their own address from the API instead.
 */
export const appOf = (key: string): AppName | null => (NAMES.has(key) ? (key as AppName) : null);

/** Whether this app serves a section itself. The shell serves them all. */
export const isOurs = (app: AppName): boolean => !THIS_APP || THIS_APP === app;

const LABELS: Record<AppName, string> = {
  exec: "Executive Admin",
  crm: "CRM",
  finance: "Finance",
  inventory: "Inventory",
  regulatory: "Regulatory",
  inlicensing: "In-Licensing",
  pharmacy: "Pharmacy",
  platform: "Platform",
};

/**
 * What an app is called.
 *
 * The name of the app, never the name of a screen in it: "Admin", not
 * "Settings"; "Platform", not "Companies". A list of apps that names one of
 * them by its front screen is a list of two different things.
 */
export const appLabel = (app: AppName): string => LABELS[app];

/**
 * What this app calls itself, or null in the shell, which is all of them.
 *
 * Each app signs in on its own page, and the page says which one it is: the
 * session is shared, so somebody arriving at a sign-in screen should be able
 * to see what they are about to enter rather than infer it from the port.
 */
export const thisAppLabel = (): string | null => (THIS_APP ? LABELS[THIS_APP] : null);

/**
 * The companies list, which is the Platform app's.
 *
 * The shell mounts it at `/platform`; the app itself serves it at its own root;
 * from anywhere else it is that app's address. One screen, three ways of
 * reaching it, and this is the one place that knows which is in use.
 */
export const platformHome = (): string =>
  !THIS_APP ? "/platform" : THIS_APP === "platform" ? "/" : appUrl("platform");

/**
 * Whether this person can use an app at all.
 *
 * Each answer is the gate that app already applies inside — Admin's two keys,
 * the platform tier, holding the module — asked at the door instead of three
 * screens in. Signing somebody in and then turning them away is the same "no"
 * delivered later, with their session left open behind it.
 *
 * The seven are one module each, so for those the question is simply whether
 * this person holds it.
 */
export function canUseApp(app: AppName, me: Me): boolean {
  switch (app) {
    case "platform":
      return me.isDeveloperAdmin;
    // The CRM is seven divisions over one workspace, so any one of them opens it.
    case "crm":
      return me.modules.some((m) => m.kind === "crm");
    // Executive Admin is a department like the rest, and also where the
    // company's own controls live, so either way in opens it.
    case "exec":
      return me.modules.some((m) => m.key === "exec") || me.canManageSettings || me.canRecover;
    case "finance":
    case "inventory":
    case "regulatory":
    case "inlicensing":
    case "pharmacy":
      return me.modules.some((m) => m.key === app);
  }
}

/** The same question for the app this is running in. The shell is every app at once, so it turns nobody away. */
export const canUseThisApp = (me: Me): boolean => (THIS_APP ? canUseApp(THIS_APP, me) : true);

// Whose work comes first when somebody has several: the company's own view,
// then the divisions that sell, then the departments behind them.
const HOME_ORDER: readonly AppName[] = [
  "exec",
  "crm",
  "finance",
  "inventory",
  "regulatory",
  "inlicensing",
  "pharmacy",
  "platform",
];

/**
 * The app to send somebody to when the one they tried is not theirs.
 *
 * Null when none of them is: there is no app every person can open, so this
 * has to be able to say so. Sending them on to a second app that would turn
 * them away as well is how a bounce becomes a loop between two front doors.
 */
export function homeApp(me: Me): AppName | null {
  // A Developer Admin who has opened no company belongs on the platform: that
  // is where a company is chosen, and everything else waits on it.
  if (me.isDeveloperAdmin && me.org === null) return "platform";
  return HOME_ORDER.find((a) => canUseApp(a, me)) ?? null;
}

/**
 * Where a module's screens sit, as a prefix.
 *
 * The shell mounts every module under `/m/<key>`; the module's own app serves
 * the same screens at its own root, so there the prefix is nothing at all. A
 * screen that links to its own pages asks here rather than writing either one,
 * which is what lets the same screen be right in both places.
 */
export function moduleBase(key: string): string {
  const app = appOf(key);
  return app && THIS_APP === app ? "" : `/m/${key}`;
}
