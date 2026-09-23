import type { CustomEntity } from "@/src/platform/lib/types";

/** The records custom fields go on, as Settings names them. */
export const ENTITY_WORDS: Record<CustomEntity, { one: string; many: string }> = {
  company: { one: "customer", many: "Customers" },
  contact: { one: "contact", many: "Contacts" },
  product: { one: "product", many: "Products" },
  quote: { one: "quote", many: "Quotes" },
};
