import { Building2, FlaskConical, HeartPulse, Landmark, Network, Package, ShieldCheck, Users, type LucideIcon } from "lucide-react";

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

export type ModuleKey = "platform" | "crm" | "inventory" | "finance" | "admin" | "pharmacy" | "inlicensing" | "regulatory";

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
  { key: "finance", path: "/finance", label: "Finance", blurb: "Invoices and tax", appKey: "finance", apiEnv: "FINANCE_API_URL", apiLocal: "http://127.0.0.1:8303", status: "live", icon: Landmark, tint: "#fcf3dd", ink: "#9a6a12" },
  { key: "pharmacy", path: "/pharmacy", label: "Pharmacy", blurb: "Prescriptions", appKey: "pharmacy", apiEnv: "PHARMACY_API_URL", apiLocal: "http://127.0.0.1:8307", status: "live", icon: HeartPulse, tint: "#fbe7e3", ink: "#c2493a" },
  { key: "admin", path: "/admin", label: "Executive Admin", blurb: "Company settings", appKey: "exec", apiEnv: "ADMIN_API_URL", apiLocal: "http://127.0.0.1:8300", status: "live", icon: Building2, tint: "#efeafb", ink: "#7a5cc4" },
  { key: "inlicensing", path: "/in-licensing", label: "In-Licensing", blurb: "Product licensing", appKey: "inlicensing", apiEnv: "INLICENSING_API_URL", apiLocal: "http://127.0.0.1:8306", status: "soon", icon: FlaskConical, tint: "#e6f3f3", ink: "#2f7d7d" },
  { key: "regulatory", path: "/regulatory", label: "Regulatory", blurb: "Registrations and permits", appKey: "regulatory", apiEnv: "REGULATORY_API_URL", apiLocal: "http://127.0.0.1:8308", status: "soon", icon: ShieldCheck, tint: "#eef1f6", ink: "#4a5b78" },
  // The Admin Console (decided 2026-10-24): on the Bishnoi One account itself, no module session. Platform
  // staff (same email) see APIs, companies and accounts; a company's administrators its roles.
  { key: "platform", path: "/platform", label: "Admin Console", blurb: "APIs, companies, accounts and roles", appKey: "platform", apiEnv: "PLATFORM_API_URL", apiLocal: "http://127.0.0.1:8305", status: "live", accountOnly: true, icon: Network, tint: "#fdeedf", ink: "#b75a10" },
];

export const moduleByKey = (key: string | null | undefined): ModuleDef | null => MODULES.find((m) => m.key === key) ?? null;

export const moduleByAppKey = (appKey: string): ModuleDef | null => MODULES.find((m) => m.appKey === appKey) ?? null;

/** The module a path on this site belongs to: /crm and /crm/deals are the CRM's; / is nobody's. */
export function moduleOfPath(pathname: string): ModuleDef | null {
  // The longest path that fits, should one module ever sit under another.
  return MODULES.filter((m) => pathname === m.path || pathname.startsWith(`${m.path}/`)).sort((a, b) => b.path.length - a.path.length)[0] ?? null;
}

/** Whether a path is one of its module's public pages (no sign-in needed). */
export const isPublicPath = (m: ModuleDef, pathname: string): boolean =>
  (m.public ?? []).some((p) => pathname === p || pathname.startsWith(`${p}/`));
