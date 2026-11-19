import type { Me } from "@/src/modules/finance/platform/lib/types";

// Finance's areas, each one sidebar row with its pages as tabs at the top (decided 2026-11-04, vault
// Plans/Plan - Shorter Finance sidebar 2026-11-04): the menu had grown to 27 rows. As Marketing
// requests did, but every page keeps its own address, so bookmarks, Overview links and the links the
// API sends (lib/links.ts screen()) still open the same page. The sidebar (nav.tsx) and the tab strip
// (section-tabs.tsx) both read this list.

/** What each page needs, so the menu offers only what the role opens (the API checks the same). A list means any one of them. */
export const NEEDS: [string, string | string[]][] = [
  ["/finance/import-review", "integrations.manage"],
  ["/finance/import-matching", ["imports.propose", "imports.confirm", "imports.confirm_tax", "imports.run"]],
  ["/finance/funds", "funds.view"],
  ["/finance/invoices", "invoices.view"],
  ["/finance/sales-orders", "sales_orders.view"],
  ["/finance/bills", "bills.view"],
  ["/finance/suppliers", "suppliers.view"],
  ["/finance/vouchers", "vouchers.view"],
  ["/finance/petty-cash", "petty_cash.view"],
  ["/finance/bank", "bank.view"],
  ["/finance/ledger/accounts", "accounts.view"],
  ["/finance/ledger/posting", "accounts.view"],
  ["/finance/ledger/categories", "categories.view"],
  ["/finance/ledger", "journal.view"],
  ["/finance/tax", "tax.view"],
  ["/finance/prices", "prices.view"],
  // Preparing BIR files is its own tick; the reports and books are bir.view.
  ["/finance/bir/sales-dat", "bir.prepare"],
  ["/finance/bir", "bir.view"],
  ["/finance/calendar", "calendar.use"],
  ["/finance", "dashboard.view"],
];

/** Whether this person may open the page at `href` (its path, without the query). */
export function opens(me: Me, href: string): boolean {
  const may = (p: string) => me.permissions?.includes(p) ?? false;
  const rule = NEEDS.find(([at]) => (at === "/finance" ? href === at : href === at || href.startsWith(`${at}/`)));
  if (!rule) return true;
  return Array.isArray(rule[1]) ? rule[1].some(may) : may(rule[1]);
}

export type SectionTab = { href: string; label: string };
/**
 * `foot`: at the bottom of the sidebar, with the settings. `exact`: a one-page area whose row lights only on that page.
 * `also`: other pages, not tabs, on which the area's row stays lit.
 */
export type Section = { key: string; label: string; icon: string; tabs: SectionTab[]; foot?: boolean; exact?: boolean; also?: string[] };

// In the order of Zoho Books' menu (decided 2026-10-24): money out, money in, banking, the books, taxes.
export const SECTIONS: Section[] = [
  { key: "payables", label: "Payables", icon: "orders", tabs: [
    { href: "/finance/bills", label: "Bills" },
    { href: "/finance/vouchers", label: "Payment vouchers" },
    { href: "/finance/bills/aging", label: "Supplier aging" },
    { href: "/finance/suppliers", label: "Suppliers" },
  ] },
  // Petty cash (2026-10-30), and the expenses brought in from Zoho Books' file (2026-10-31): renamed from
  // "Imported expenses" on 2026-11-04, which read as the costs of importing goods.
  { key: "petty-cash", label: "Petty cash", icon: "money", tabs: [
    { href: "/finance/petty-cash", label: "Petty cash" },
    { href: "/finance/petty-cash/imported", label: "Zoho expense history" },
  ] },
  { key: "sales", label: "Sales", icon: "letters", tabs: [
    { href: "/finance/sales-orders", label: "Sales orders" },
    { href: "/finance/invoices", label: "Finance invoices" },
    { href: "/finance/invoices/zoho", label: "Zoho invoices" },
    { href: "/finance/invoices/receivables", label: "Receivables" },
  ] },
  // A cash advance released, its liquidation reviewed, then settled: one page with a tab per stage (screens/funds.tsx).
  { key: "funds", label: "Marketing requests", icon: "payments", tabs: [{ href: "/finance/funds", label: "Marketing requests" }] },
  { key: "prices", label: "Price approvals", icon: "pricing", tabs: [{ href: "/finance/prices", label: "Price approvals" }] },
  { key: "banking", label: "Banking", icon: "money", tabs: [
    { href: "/finance/bank", label: "Bank reconciliation" },
    { href: "/finance/bank/accounts", label: "Bank accounts and rates" },
  ] },
  // Used every day, so its own row; the rest of the books is month-end and setup.
  { key: "journal", label: "Journal entries", icon: "lists", exact: true, tabs: [{ href: "/finance/ledger", label: "Journal entries" }] },
  { key: "books", label: "Books and closing", icon: "reports", tabs: [
    { href: "/finance/ledger/trial-balance", label: "Trial balance" },
    { href: "/finance/ledger/closing", label: "Closing and equity" },
    { href: "/finance/ledger/accounts", label: "Chart of accounts" },
    { href: "/finance/ledger/fixed-assets", label: "Fixed assets" },
    { href: "/finance/ledger/budgets", label: "Budgets" },
  ] },
  // Readiness first: it says what's missing before a form is opened.
  { key: "taxes", label: "Taxes", icon: "money", tabs: [
    { href: "/finance/bir/readiness", label: "BIR readiness" },
    { href: "/finance/bir/vat", label: "VAT return" },
    { href: "/finance/bir/withholding", label: "Withholding tax" },
    { href: "/finance/bir/lists", label: "Summary lists" },
    { href: "/finance/bir/sales-dat", label: "BIR files (DAT)" },
  ] },
  { key: "calendar", label: "Calendar", icon: "calendar", tabs: [{ href: "/finance/calendar", label: "Calendar" }] },
  // The financial statements and the books of accounts are in the Reports Center (2026-10-28).
  { key: "reports", label: "Reports", icon: "reports", also: ["/finance/bir/statements"], tabs: [{ href: "/finance/reports", label: "Reports" }] },
  { key: "imports", label: "Imports", icon: "lists", foot: true, tabs: [
    { href: "/finance/import-matching", label: "Import matching" },
    { href: "/finance/import-review", label: "Import review" },
  ] },
];

/** The areas this person sees, each with only the tabs they may open; an area with none is left out. */
export function sectionsFor(me: Me): Section[] {
  return SECTIONS.map((s) => ({ ...s, tabs: s.tabs.filter((t) => opens(me, t.href)) })).filter((s) => s.tabs.length > 0);
}

/** The area whose tab is this page, exactly: tabs show on an area's own pages, not on a record or a form inside one. */
export function sectionAt(sections: Section[], pathname: string): Section | undefined {
  return sections.find((s) => s.tabs.some((t) => t.href === pathname));
}
