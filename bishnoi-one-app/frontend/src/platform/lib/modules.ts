import { Building2, FlaskConical, HeartPulse, Landmark, Network, Package, ShieldCheck, Users, Wrench, type LucideIcon } from "lucide-react";

// Every Bishnoi One module in the one app (decided 2026-10-23,
// benchmarks/decisions.md): where its screens live on this site, which API it
// talks to, and its key on Bishnoi One Platform. Each module keeps its own API
// and database; only the screens are together, under its path.
//
// status says where its screens are today:
//   live    here, under its path (the proxy opens its session on first use);
//   moving  still in its old app while it's being brought in (linked from here);
//   soon    not built yet (a "Coming soon" page, for companies that have it).
// A module brought in (Phase 2) changes from "moving" to "live" here, and that's all.

export type ModuleKey = "platform" | "operations" | "crm" | "inventory" | "finance" | "admin" | "pharmacy" | "inlicensing" | "regulatory";

export type ModuleDef = {
  key: ModuleKey;
  /** Its screens' path on this site. */
  path: string;
  label: string;
  /** What it's for, on its tile. */
  blurb: string;
  /** Its key on Bishnoi One Platform (Applications, passes, grants). */
  appKey: string;
  /** The setting with its API's address, and the address on this computer. */
  apiEnv: string;
  apiLocal: string;
  status: "live" | "moving" | "soon";
  /** Works on the Bishnoi One account itself: no module session is opened for it. */
  accountOnly?: boolean;
  /** Its pages anyone may open, signed in or not (a customer's order link): still its module's, with no session. */
  public?: string[];
  icon: LucideIcon;
  tint: string;
  ink: string;
};

export const MODULES: ModuleDef[] = [
  { key: "crm", path: "/crm", label: "CRM", blurb: "Customers and sales", appKey: "crm", apiEnv: "CRM_API_URL", apiLocal: "http://127.0.0.1:8302", status: "live", public: ["/crm/order"], icon: Users, tint: "#e9f0fb", ink: "#4c78c8" },
  { key: "inventory", path: "/inventory", label: "Inventory", blurb: "Stock and orders", appKey: "inventory", apiEnv: "INVENTORY_API_URL", apiLocal: "http://127.0.0.1:8304", status: "live", icon: Package, tint: "#e7f1ea", ink: "#3f5e4a" },
  // The Sales app (feature plan step 11): its own place, running in the Operations service (Inventory's API,
  // its Platform key), shown to whoever has Inventory while the company's catalogue has Sales on (src/one/mine.ts).
  { key: "finance", path: "/finance", label: "Finance", blurb: "Invoices and tax", appKey: "finance", apiEnv: "FINANCE_API_URL", apiLocal: "http://127.0.0.1:8303", status: "live", icon: Landmark, tint: "#fcf3dd", ink: "#9a6a12" },
  { key: "pharmacy", path: "/pharmacy", label: "Pharmacy", blurb: "Prescriptions", appKey: "pharmacy", apiEnv: "PHARMACY_API_URL", apiLocal: "http://127.0.0.1:8307", status: "live", icon: HeartPulse, tint: "#fbe7e3", ink: "#c2493a" },
  { key: "admin", path: "/admin", label: "Executive Admin", blurb: "Office administration", appKey: "exec", apiEnv: "ADMIN_API_URL", apiLocal: "http://127.0.0.1:8300", status: "live", icon: Building2, tint: "#efeafb", ink: "#7a5cc4" },
  { key: "inlicensing", path: "/in-licensing", label: "In-Licensing", blurb: "Product licensing", appKey: "inlicensing", apiEnv: "INLICENSING_API_URL", apiLocal: "http://127.0.0.1:8306", status: "soon", icon: FlaskConical, tint: "#e6f3f3", ink: "#2f7d7d" },
  { key: "regulatory", path: "/regulatory", label: "Regulatory", blurb: "Registrations and permits", appKey: "regulatory", apiEnv: "REGULATORY_API_URL", apiLocal: "http://127.0.0.1:8308", status: "soon", icon: ShieldCheck, tint: "#eef1f6", ink: "#4a5b78" },
  // The Admin Console (decided 2026-10-24): on the Bishnoi One account itself, no module session. Platform
  // staff (same email) see APIs, companies and accounts; a company's administrators its roles.
  { key: "platform", path: "/platform", label: "Admin Console", blurb: "Your company: profile, people, roles, apps and reports", appKey: "platform", apiEnv: "PLATFORM_API_URL", apiLocal: "http://127.0.0.1:8305", status: "live", accountOnly: true, icon: Network, tint: "#fdeedf", ink: "#b75a10" },
  // Bishnoi One Operations (2026-10-30): Bishnoi One's own operators only, apart from any company's Admin Console:
  // every company, accounts and operators, the services and their connections, and troubleshooting (events).
  { key: "operations", path: "/operations", label: "Operations", blurb: "Bishnoi One: companies, services and troubleshooting", appKey: "platform", apiEnv: "PLATFORM_API_URL", apiLocal: "http://127.0.0.1:8305", status: "live", accountOnly: true, icon: Wrench, tint: "#eef1f6", ink: "#4a5b78" },
];

export const moduleByKey = (key: string | null | undefined): ModuleDef | null => MODULES.find((m) => m.key === key) ?? null;

export const moduleByAppKey = (appKey: string): ModuleDef | null => MODULES.find((m) => m.appKey === appKey) ?? null;

/** The module a path on this site belongs to: /crm and /crm/deals are the CRM's; / is nobody's. */
export function moduleOfPath(pathname: string): ModuleDef | null {
  // The longest path that fits, should one module ever sit under another.
  return MODULES.filter((m) => pathname === m.path || pathname.startsWith(`${m.path}/`)).sort((a, b) => b.path.length - a.path.length)[0] ?? null;
}

// Pages in one module's frame that run on another's API (decided 2026-10-30: sales orders are kept by
// Inventory, the Operations service, and worked in the CRM, not in an app of their own). The page and its
// actions talk to `module`; the sidebar, menu and who-you-are around it are the `frame`'s.
const BORROWED: { path: string; module: ModuleKey; frame: ModuleKey }[] = [
  { path: "/crm/sales", module: "inventory", frame: "crm" },
  // Finance's Zoho Books sign-in, under the Admin Console's Integrations (2026-10-31): kept by Finance, set up there.
  { path: "/platform/company/integrations/zoho", module: "finance", frame: "platform" },
  // Each app's settings, for company administrators only, in the Admin Console (2026-10-31): the CRM's first.
  { path: "/platform/settings/crm", module: "crm", frame: "platform" },
  { path: "/platform/settings/inventory", module: "inventory", frame: "platform" },
  { path: "/platform/settings/finance", module: "finance", frame: "platform" },
];

/** The borrowed pages a path is one of, or null. */
export const borrowedOf = (pathname: string) => BORROWED.find((b) => pathname === b.path || pathname.startsWith(`${b.path}/`)) ?? null;

/** Whether a path is one of its module's public pages (no sign-in needed). */
export const isPublicPath = (m: ModuleDef, pathname: string): boolean =>
  (m.public ?? []).some((p) => pathname === p || pathname.startsWith(`${p}/`));
