// One menu by work (stage M4 of docs/architecture/one-backend-plan.md, agreed 2026-11-18 from
// Desktop/bishnoi-one-menu-by-work.html): one sidebar for everybody, grouped by the work, not by app.
// Every page keeps its address; a group only lists what the person's role allows in the module that
// keeps the page (Platform /identity/me apps[].permissions; null = every page of that module). The
// page itself still checks. Built on the server from the account; drawn by src/platform/shell/sidebar.tsx.
//
// Pages that exist twice today (CRM products and Inventory items, vendors and suppliers, the two sales
// order lists, two calendars) are placed as they are; merging them is Step 3, one at a time with the owner.
// Promotional materials are one row, opening the step of the work the person does (Office designs,
// Pharmacy reviews, CRM gives them out).

import type { Account } from "@/src/platform/lib/account";
import type { IconName } from "@/src/platform/ui/icons";
import { CRM_SETTINGS, FINANCE_SETTINGS, FINANCE_TABS, INVENTORY_SETTINGS, INVENTORY_TABS } from "@/src/one/admin-console/app-settings";

export type MenuStep = { href: string; label: string; icon: IconName; also?: string[]; exact?: boolean };
export type MenuGroup = { label: string; icon: IconName; steps: MenuStep[] };
export type OneMenu = { home: MenuStep; processes: MenuGroup[]; foot: MenuGroup[] };

/** Every module's Reports Center: the one Reports row is current on any of them. */
export const REPORT_PATHS = [
  "/reports", "/crm/reports", "/inventory/reports", "/inventory/alerts", "/inventory/serials", "/inventory/movements",
  "/finance/reports", "/finance/bir/statements", "/admin/reports", "/pharmacy/reports", "/platform/reports",
];

type Page = MenuStep & { show: boolean };

export function buildMenu(me: Account): OneMenu {
  const apps = new Map(me.apps.map((a) => [a.key, a]));
  /** Any one of the permissions in that module (by its Platform key); a module given with no list reaches everything. */
  const may = (app: string, ...perms: string[]) => {
    const a = apps.get(app);
    if (!a) return false;
    if (a.permissions == null) return true;
    return perms.length === 0 || perms.some((p) => a.permissions!.includes(p));
  };
  const has = (app: string) => apps.has(app);
  const admin = me.isCompanyAdmin;
  // The CRM's field agent (as its own menu decided): visits, not quotes or team goals. Their customers are their doctors.
  const agent = may("crm", "visits.create") && !may("crm", "quotes.view") && !may("crm", "goals.view") && apps.get("crm")?.permissions != null;
  const sells = has("crm") && !agent;
  const keep = (pages: Page[]): MenuStep[] => pages.filter((p) => p.show).map(({ show: _s, ...step }) => step);
  const group = (label: string, icon: IconName, pages: Page[]): MenuGroup => ({ label, icon, steps: keep(pages) });

  // Promotional materials: one row, at the step this person works (design, review, giving out).
  const materials: Page = may("exec", "materials.view")
    ? { href: "/admin/materials", label: "Promotional materials", icon: "approvals", also: ["/pharmacy/material-reviews", "/crm/materials"], show: true }
    : may("pharmacy", "materials.view")
      ? { href: "/pharmacy/material-reviews", label: "Promotional materials", icon: "approvals", also: ["/admin/materials", "/crm/materials"], show: true }
      : { href: "/crm/materials", label: "Promotional materials", icon: "approvals", also: ["/admin/materials", "/pharmacy/material-reviews"], show: may("crm", "department.manage", "admin.settings") };

  const processes: MenuGroup[] = [
    group("Customers", "customers", [
      { href: "/crm/customers", label: "Customers", icon: "customers", show: sells && may("crm", "customers.view") },
      { href: "/crm/contacts", label: "Contacts", icon: "person", show: sells && may("crm", "customers.view") },
      { href: "/crm/activities", label: "Activities", icon: "activity", also: ["/crm/follow-ups"], show: sells && may("crm", "activities.view") },
      { href: "/crm/calendar", label: "Calendar", icon: "calendar", show: may("crm", "activities.view") },
      { href: "/crm/retention", label: "Retention", icon: "retention", show: sells && may("crm", "customers.view") },
      { href: "/crm/media", label: "Customer documents", icon: "letters", show: may("crm", "customers.view", "admin.settings") },
    ]),
    group("Selling", "deals", [
      { href: "/crm", label: "Sales overview", icon: "overview", exact: true, show: has("crm") },
      { href: "/crm/deals", label: "Deals", icon: "deals", show: sells && may("crm", "deals.view") },
      { href: "/crm/quotes", label: "Quotes", icon: "quotes", show: sells && may("crm", "quotes.view") },
      { href: "/crm/sales", label: "Sales orders", icon: "issuance", show: sells && may("crm", "quotes.view") },
      { href: "/crm/order-links", label: "Order links", icon: "orders", show: sells && may("crm", "quotes.view") },
      { href: "/crm/products", label: "Products and prices", icon: "products", show: may("crm", "products.view") },
      { href: "/crm/prices", label: "Price books", icon: "pricing", show: may("crm", "products.prices") },
      { href: "/crm/promos", label: "Promotions", icon: "promos", show: may("crm", "products.view") },
      { href: "/crm/bundles", label: "Bundles", icon: "bundles", show: may("crm", "products.view") },
      { href: "/finance/prices", label: "Price approvals", icon: "pricing", show: may("finance", "prices.view") },
    ]),
    // Field agents aren't CRM sales agents (owner, 2026-11-17): their own group, their own goals.
    group("Field", "visit", [
      { href: "/crm/field", label: "Team progress", icon: "goals", exact: true, also: ["/crm/field/goals", "/crm/field/balances"], show: may("crm", "goals.view") },
      { href: "/crm/field/doctors", label: "Accounts to visit", icon: "customers", also: agent ? ["/crm/customers", "/crm/contacts"] : [], show: may("crm", "visits.view") },
      { href: "/crm/field/routes", label: agent ? "My route" : "Routes", icon: "trend", show: may("crm", "goals.view") || agent },
      { href: "/crm/visits", label: "Visits", icon: "visit", show: may("crm", "visits.view") },
      { href: "/crm/field/assistance", label: "Patient assistance", icon: "approvals", show: may("crm", "visits.view") },
    ]),
    group("Stock", "stock", [
      { href: "/inventory", label: "Stock overview", icon: "overview", exact: true, show: may("inventory", "dashboard.view") },
      { href: "/inventory/products", label: "Items", icon: "products", exact: true, also: ["/inventory/products"], show: may("inventory", "products.view") },
      { href: "/inventory/products/cpr", label: "Item registrations (CPR)", icon: "info", show: may("inventory", "products.view") },
      { href: "/inventory/stock", label: "Stock on hand", icon: "stock", show: may("inventory", "stock.view") },
      { href: "/inventory/scan", label: "Scan", icon: "scan", show: may("inventory", "stock.view") },
      { href: "/inventory/transfers", label: "Transfer orders", icon: "transfers", show: may("inventory", "transfers.view") },
      { href: "/inventory/adjustments", label: "Inventory adjustments", icon: "adjustments", show: may("inventory", "adjustments.view") },
      { href: "/inventory/counts", label: "Inventory counts", icon: "counts", show: may("inventory", "counts.view") },
      { href: "/inventory/warehouses", label: "Warehouses", icon: "warehouses", show: may("inventory", "warehouses.view") },
    ]),
    // Buying, in the order it happens: the vendor, what to order, the order, the goods received and checked.
    group("Buying", "purchaseOrders", [
      { href: "/inventory/suppliers", label: "Vendors", icon: "suppliers", show: may("inventory", "suppliers.view") },
      { href: "/inventory/replenishment", label: "Replenishment", icon: "reorder", show: may("inventory", "purchasing.view") },
      { href: "/inventory/purchase-orders", label: "Purchase orders", icon: "purchaseOrders", also: ["/inventory/backorders"], show: may("inventory", "purchasing.view") },
      { href: "/inventory/receipts", label: "Purchase receives", icon: "receiving", show: may("inventory", "receiving.view") },
      { href: "/inventory/quality-checks", label: "Quality checks", icon: "approvals", show: may("inventory", "receiving.view") },
      { href: "/inventory/consignment", label: "Consignment", icon: "suppliers", show: may("inventory", "purchasing.view") },
    ]),
    group("Deliveries", "issuance", [
      { href: "/inventory/orders", label: "Deliveries", icon: "issuance", show: may("inventory", "orders.view") },
      { href: "/inventory/reservations", label: "Reservations", icon: "reservations", show: may("inventory", "orders.view") },
    ]),
    group("Money", "money", [
      { href: "/finance", label: "Finance overview", icon: "overview", exact: true, show: may("finance", "dashboard.view") },
      { href: "/finance/invoices", label: "Invoices", icon: "letters", exact: true, show: may("finance", "invoices.view") },
      { href: "/finance/invoices/receivables", label: "Receivables", icon: "money", show: may("finance", "invoices.view") },
      { href: "/finance/sales-orders", label: "Finance sales orders", icon: "orders", show: may("finance", "sales_orders.view") },
      { href: "/finance/bills", label: "Bills", icon: "orders", exact: true, show: may("finance", "bills.view") },
      { href: "/finance/bills/aging", label: "Supplier aging", icon: "reports", show: may("finance", "bills.view") },
      { href: "/finance/vouchers", label: "Payment vouchers", icon: "payments", show: may("finance", "vouchers.view") },
      { href: "/finance/suppliers", label: "Suppliers", icon: "people", show: may("finance", "suppliers.view") },
      { href: "/finance/petty-cash", label: "Petty cash", icon: "money", exact: true, show: may("finance", "petty_cash.view") },
      { href: "/finance/funds", label: "Marketing requests", icon: "payments", show: may("finance", "funds.view") },
      { href: "/finance/bank/accounts", label: "Bank accounts", icon: "money", show: may("finance", "bank.view") },
      { href: "/finance/bank", label: "Bank reconciliation", icon: "money", exact: true, show: may("finance", "bank.view") },
    ]),
    group("Accounting", "lists", [
      { href: "/finance/ledger", label: "Journal entries", icon: "lists", exact: true, show: may("finance", "journal.view") },
      { href: "/finance/ledger/accounts", label: "Chart of accounts", icon: "lists", show: may("finance", "accounts.view") },
      { href: "/finance/ledger/trial-balance", label: "Trial balance", icon: "reports", show: may("finance", "journal.view") },
      { href: "/finance/ledger/closing", label: "Closing and equity", icon: "lists", show: may("finance", "journal.view") },
      { href: "/finance/ledger/fixed-assets", label: "Fixed assets", icon: "lists", show: may("finance", "journal.view") },
      { href: "/finance/ledger/budgets", label: "Budgets", icon: "reports", show: may("finance", "journal.view") },
      { href: "/finance/bir/vat", label: "VAT return", icon: "money", show: may("finance", "bir.view") },
      { href: "/finance/bir/withholding", label: "Withholding tax", icon: "letters", show: may("finance", "bir.view") },
      { href: "/finance/bir/lists", label: "Summary lists", icon: "lists", show: may("finance", "bir.view") },
      { href: "/finance/bir/sales-dat", label: "BIR files (DAT)", icon: "letters", show: may("finance", "bir.prepare") },
      { href: "/finance/bir/readiness", label: "BIR readiness", icon: "lists", show: may("finance", "bir.view") },
      { href: "/finance/calendar", label: "Signing calendar", icon: "calendar", show: may("finance", "calendar.use") },
      { href: "/finance/petty-cash/imported", label: "Imported expenses", icon: "lists", show: may("finance", "petty_cash.view") },
      { href: "/finance/import-review", label: "Import review", icon: "lists", show: may("finance", "integrations.manage") },
      { href: "/finance/import-matching", label: "Import matching", icon: "lists", show: may("finance", "imports.propose", "imports.confirm", "imports.confirm_tax", "imports.run") },
    ]),
    group("Pharmacy", "prescriptions", [
      { href: "/pharmacy", label: "Pharmacy overview", icon: "overview", exact: true, show: may("pharmacy", "dashboard.view") },
      { href: "/pharmacy/prescriptions", label: "Prescriptions", icon: "prescriptions", show: may("pharmacy", "prescriptions.view") },
      { href: "/pharmacy/dispensing", label: "Dispensing", icon: "dispensing", show: may("pharmacy", "dispensing.view") },
      { href: "/pharmacy/sales", label: "Pharmacy sales", icon: "sales", show: may("pharmacy", "sales.view") },
      { href: "/pharmacy/patients", label: "Patients and customers", icon: "patients", show: may("pharmacy", "patients.view") },
      { href: "/pharmacy/medicines", label: "Medicines", icon: "medicines", show: may("pharmacy", "medicines.view") },
      { href: "/pharmacy/batches", label: "Batches and expiry", icon: "batches", show: may("pharmacy", "batches.view") },
      { href: "/pharmacy/stock", label: "Pharmacy stock", icon: "stock", show: may("pharmacy", "stock.view") },
      { href: "/pharmacy/suppliers", label: "Pharmacy suppliers", icon: "suppliers", show: may("pharmacy", "suppliers.view") },
      { href: "/pharmacy/admin/settings", label: "Pharmacy settings", icon: "settings", also: ["/pharmacy/admin"], show: may("pharmacy", "admin.settings") },
    ]),
    group("Office", "properties", [
      { href: "/admin", label: "Office overview", icon: "overview", exact: true, show: may("exec", "dashboard.view") },
      { href: "/admin/notifications", label: "Renewal alerts", icon: "notifications", show: may("exec", "notifications.view") },
      { href: "/admin/permits", label: "Permits", icon: "permits", show: may("exec", "permits.view") },
      { href: "/admin/documents", label: "Company documents", icon: "documents", show: may("exec", "documents.view") },
      { href: "/admin/immigration", label: "Expatriates", icon: "immigration", show: may("exec", "immigration.view") },
      { href: "/admin/properties", label: "Properties", icon: "properties", show: may("exec", "properties.view") },
      { href: "/admin/vehicles", label: "Vehicles", icon: "vehicles", show: may("exec", "vehicles.view") },
      { href: "/admin/fuel-cards", label: "Fuel cards", icon: "fuelCards", show: may("exec", "vehicles.view") },
      { href: "/admin/travel", label: "Hotel and flights", icon: "travel", show: may("exec", "travel.view") },
      { href: "/admin/devices", label: "Devices issued", icon: "devices", show: may("exec", "devices.view") },
      { href: "/admin/tickets", label: "Office requests", icon: "tickets", show: may("exec", "tickets.view") },
      materials,
    ]),
    group("Team", "people", [
      { href: "/platform/home", label: "Employee overview", icon: "overview", show: admin },
      { href: "/platform/roles/people", label: "Employees", icon: "people", show: admin },
      // HR who aren't administrators (step 4I); administrators open HR records on Employees.
      { href: "/platform/hr", label: "HR records", icon: "documents", show: !admin && !!me.hrRecords },
      { href: "/platform/organisation", label: "Organisation", icon: "teams", show: admin },
      { href: "/platform/roles", label: "Roles", icon: "roles", exact: true, show: admin },
      { href: "/crm/performance", label: "Targets and KPIs", icon: "goals", also: ["/crm/kpis"], show: sells && may("crm", "goals.view") },
    ]),
  ];
  // One Reports row for everybody who has any: the one Reports Center lists each part's reports (app/(app)/reports).
  const reports = reportCentres(me);
  if (reports.length > 0) processes.push({ label: "Reports", icon: "reports", steps: [{ href: "/reports", label: "Reports", icon: "reports", also: REPORT_PATHS }] });

  const foot: MenuGroup[] = [
    group("Admin", "settings", [
      { href: "/platform/company", label: "Company profile", icon: "company", show: admin },
      { href: "/platform/company/security", label: "Security", icon: "password", show: admin },
      { href: "/platform/company/activity", label: "Activity log", icon: "auditLog", show: admin },
      { href: "/platform/company/data-cleanup", label: "Data clean-up", icon: "lists", show: admin },
      { href: `${CRM_SETTINGS}/company`, label: "CRM settings", icon: "deals", also: [CRM_SETTINGS], show: admin && has("crm") },
      { href: INVENTORY_TABS[0].href, label: "Inventory settings", icon: "inventory", also: [INVENTORY_SETTINGS], show: admin && has("inventory") },
      { href: FINANCE_TABS[0].href, label: "Finance settings", icon: "finance", also: [FINANCE_SETTINGS], show: admin && has("finance") },
      { href: "/platform/company/integrations", label: "Integrations", icon: "settings", show: admin },
    ]),
    // Bishnoi One's own running, for its operators only (2026-10-30).
    group("Operations", "companies", [
      { href: "/operations/companies", label: "Companies", icon: "companies", show: Boolean(me.staff) },
      { href: "/operations/people", label: "Find a person", icon: "person", show: Boolean(me.staff) },
      { href: "/operations/operators", label: "Operators", icon: "people", show: Boolean(me.staff) },
      { href: "/operations/apis", label: "Services and connections", icon: "apps", show: Boolean(me.staff) },
      { href: "/operations/events", label: "Events between modules", icon: "activity", show: Boolean(me.staff) },
    ]),
  ];
  return { home: { href: "/", label: "Home", icon: "home", exact: true }, processes: processes.filter((g) => g.steps.length > 0), foot: foot.filter((g) => g.steps.length > 0) };
}

/** A part's Reports Center, as the one Reports page lists it. */
export type ReportCentre = { href: string; label: string; says: string; icon: IconName };

export function reportCentres(me: Account): ReportCentre[] {
  const apps = new Map(me.apps.map((a) => [a.key, a]));
  const may = (app: string, ...perms: string[]) => {
    const a = apps.get(app);
    if (!a) return false;
    return a.permissions == null || perms.length === 0 || perms.some((p) => a.permissions!.includes(p));
  };
  const out: ReportCentre[] = [];
  if (may("crm")) out.push({ href: "/crm/reports", label: "Customers and selling", says: "Pipeline, quotes, sales, field work and targets", icon: "deals" });
  if (may("inventory", "reports.view", "stock.view")) out.push({ href: "/inventory/reports", label: "Stock, buying and deliveries", says: "Stock, expiry, movements, purchasing and delivery", icon: "stock" });
  if (may("finance")) out.push({ href: "/finance/reports", label: "Money and accounting", says: "Statements, books, receivables, payables and taxes", icon: "money" });
  if (may("pharmacy", "reports.view")) out.push({ href: "/pharmacy/reports", label: "Pharmacy", says: "Prescriptions, dispensing, sales and stock", icon: "prescriptions" });
  if (may("exec", "permits.view", "immigration.view", "documents.view", "properties.view", "vehicles.view", "travel.view", "devices.view", "tickets.view", "materials.view"))
    out.push({ href: "/admin/reports", label: "Office", says: "Permits, documents, fleet, travel and requests", icon: "properties" });
  if (me.isCompanyAdmin) out.push({ href: "/platform/reports", label: "Employees", says: "People, sign-ins, access and security", icon: "people" });
  return out;
}
