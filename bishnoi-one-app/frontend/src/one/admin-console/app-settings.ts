// Each app's settings in the Admin Console (2026-11-01): one sidebar row per app under Apps, its parts as tabs
// on the page (src/platform/ui/link-tabs.tsx). The addresses are the pages' own, so old links still open the tab.
import type { LinkTab } from "@/src/platform/ui/link-tabs";

export const CRM_SETTINGS = "/platform/settings/crm";
export const INVENTORY_SETTINGS = "/platform/settings/inventory";
export const FINANCE_SETTINGS = "/platform/settings/finance";

export const INVENTORY_TABS: LinkTab[] = [
  { href: `${INVENTORY_SETTINGS}/categories`, label: "Categories" },
  { href: `${INVENTORY_SETTINGS}/brands`, label: "Brands" },
  { href: `${INVENTORY_SETTINGS}/units`, label: "Units" },
  { href: `${INVENTORY_SETTINGS}/couriers`, label: "Couriers" },
];

export const FINANCE_TABS: LinkTab[] = [
  { href: `${FINANCE_SETTINGS}/taxes`, label: "Taxes" },
  { href: `${FINANCE_SETTINGS}/number-series`, label: "Number series" },
  { href: `${FINANCE_SETTINGS}/default-accounts`, label: "Default accounts" },
  { href: `${FINANCE_SETTINGS}/expense-categories`, label: "Expense categories" },
];

/**
 * The CRM has more parts, so three tabs, each with its pages in a second row: what the company shows and sends
 * (General), how records are laid out (Customization), how selling is priced and measured (Sales and pricing).
 * The pages are the CRM's settings list (crm/lib/access.ts SETTINGS_PAGES), so each stays behind its permission.
 */
export const CRM_GROUPS: { label: string; pages: string[]; also?: string[] }[] = [
  { label: "General", pages: [`${CRM_SETTINGS}/company`, `${CRM_SETTINGS}/quote-templates`, `${CRM_SETTINGS}/emails`], also: [`${CRM_SETTINGS}/terms`] },
  { label: "Customization", pages: [CRM_SETTINGS, `${CRM_SETTINGS}/customer-types`, `${CRM_SETTINGS}/deal-stages`, `${CRM_SETTINGS}/associations`], also: [`${CRM_SETTINGS}/lists`] },
  { label: "Sales and pricing", pages: [`${CRM_SETTINGS}/pricing`, `${CRM_SETTINGS}/price-rules`, `${CRM_SETTINGS}/retention-windows`, `${CRM_SETTINGS}/performance`, `${CRM_SETTINGS}/attention`], also: [`${CRM_SETTINGS}/kpis`] },
];

/** The CRM's tabs and second rows for the pages this person may open (the CRM root is Forms: exact, not a prefix). */
export function crmTabs(allowed: { href: string; label: string }[]) {
  const tab = (p: { href: string; label: string }): LinkTab => ({ href: p.href, label: p.label, exact: p.href === CRM_SETTINGS });
  return CRM_GROUPS.map((g) => {
    const pages = g.pages.map((h) => allowed.find((p) => p.href === h)).filter((p) => p !== undefined).map(tab);
    return { label: g.label, pages, top: { href: pages[0]?.href ?? "", label: g.label, also: [...pages.filter((p) => !p.exact).map((p) => p.href), ...(g.also ?? [])], exact: pages[0]?.exact && pages.length === 1 } as LinkTab };
  }).filter((g) => g.pages.length > 0);
}
