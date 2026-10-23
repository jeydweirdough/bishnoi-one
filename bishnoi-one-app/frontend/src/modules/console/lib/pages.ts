import type { IconName } from "@/src/modules/console/platform/ui/icons";

// The console's places, as the sidebar groups them. Each place's parts
// (Companies' departments and branches, Support's kinds of ticket) are tabs
// inside it, not rows here.

export type PlatformPage = { href: string; label: string; icon: IconName };

/** Which page each thing not set up yet is fixed on (the API's /platform/unset), and what its red mark says. */
export const UNSET: Record<string, { href: string; says: (n: number) => string }> = {
  userPasswords: { href: "/platform/console/users", says: (n) => `${n} ${n === 1 ? "person has" : "people have"} no password yet, so they can't sign in` },
  applicationAddress: { href: "/platform/console/applications", says: (n) => `${n} ${n === 1 ? "application has" : "applications have"} no address` },
};

export const PLATFORM_GROUPS: { label: string; pages: PlatformPage[] }[] = [
  { label: "Platform", pages: [{ href: "/platform/console", label: "Dashboard", icon: "overview" }] },
  {
    label: "Customers",
    pages: [
      { href: "/platform/console/companies", label: "Companies", icon: "companies" },
      { href: "/platform/console/users", label: "Users", icon: "people" },
      { href: "/platform/console/access", label: "Access", icon: "roles" },
    ],
  },
  {
    label: "Service",
    pages: [
      { href: "/platform/console/applications", label: "Applications", icon: "apps" },
      { href: "/platform/console/monitoring", label: "Monitoring", icon: "monitoring" },
      { href: "/platform/console/connections", label: "Connections", icon: "teams" },
      { href: "/platform/console/incidents", label: "Incidents", icon: "incidents" },
      { href: "/platform/console/support", label: "Support", icon: "support" },
    ],
  },
  {
    label: "Oversight",
    pages: [
      { href: "/platform/console/activity", label: "Activity and audit", icon: "auditLog" },
      { href: "/platform/console/communications", label: "Communications", icon: "communications" },
      { href: "/platform/console/settings", label: "Settings", icon: "settings" },
    ],
  },
];

const within = (pathname: string, href: string) => pathname === href || pathname.startsWith(`${href}/`);

/** Where you are, for the phone's top bar. */
export function platformPlace(pathname: string): string | null {
  if (pathname === "/") return "Dashboard";
  if (within(pathname, "/platform/console/account")) return "Your profile";
  for (const group of PLATFORM_GROUPS) {
    const page = group.pages.find((p) => p.href !== "/" && within(pathname, p.href));
    if (page) return page.label;
  }
  return null;
}
