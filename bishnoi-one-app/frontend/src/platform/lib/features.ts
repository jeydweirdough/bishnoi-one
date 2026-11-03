// The company's app catalogue in the screens (feature plan step 6): which pages each catalogue app
// or feature switch hides when the company turns it off. The Platform keeps the switches
// (/identity/me "features"); the shared sidebar drops these pages, so every app hides them at once.
// A switch that hides fields or reports inside a page is checked on that page.

export type Features = Record<string, boolean>;

const PAGES: Record<string, string[]> = {
  "crm.deals": ["/crm/deals"],
  "crm.quotes": ["/crm/quotes", "/crm/order-links"],
  "crm.prices": ["/crm/prices", "/crm/promos", "/crm/bundles", "/platform/settings/crm/pricing"],
  "crm.lead_inbox": ["/crm/inbox"],
  "crm.retention": ["/crm/retention"],
  "app:field_sales": ["/crm/field", "/crm/visits"],
  "field_sales.call_plans": ["/crm/field/routes", "/crm/field/doctors"],
  "field_sales.patient_assistance": ["/crm/field/assistance"],
  "app:sales": ["/crm/sales"],
  "app:shipping": ["/inventory/couriers", "/platform/settings/inventory/couriers"],
  "warehouse.quality": ["/inventory/quality-checks"],
  "warehouse.barcodes": ["/inventory/scan"],
  "warehouse.waves": ["/inventory/waves"],
  "purchasing.auto_draft": ["/inventory/replenishment"],
  "app:purchasing": ["/inventory/suppliers", "/inventory/purchase-orders", "/inventory/receipts", "/inventory/backorders"],
  "inventory.serials": ["/inventory/serials"],
  "inventory.cpr": ["/inventory/products/cpr"],
  "inventory.warehouses": ["/inventory/transfers"],
  "inventory.counts": ["/inventory/counts"],
  "app:invoicing": ["/finance/invoices"],
  "invoicing.payments": ["/finance/invoices/receivables"],
  "accounting.funds": ["/finance/funds"],
  "accounting.bank": ["/finance/bank"],
  "accounting.bir": ["/finance/bir"],
};

/** Whether a page is hidden by a switch the company turned off (unknown switches count as on). */
export function hiddenByFeature(href: string, features: Features | null | undefined): boolean {
  if (!features) return false;
  href = href.split("?")[0];
  return Object.entries(PAGES).some(([key, pages]) => features[key] === false && pages.some((p) => href === p || href.startsWith(`${p}/`)));
}
