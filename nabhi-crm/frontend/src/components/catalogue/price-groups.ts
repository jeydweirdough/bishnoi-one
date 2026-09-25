import "server-only";
import { can } from "@/src/platform/lib/access";
import { api } from "@/src/platform/lib/api";
import type { Me } from "@/src/platform/lib/types";
import type { PriceRules } from "./price-rules-types";

/** The price groups a customer can be put in, for the customer form. None
 *  when this person can't see the price rules, or there are no groups. */
export async function priceGroupsFor(me: Me): Promise<PriceRules["groups"]> {
  if (!can(me, "products.view")) return [];
  try {
    return (await api.get<PriceRules>("/pricing/rules")).groups;
  } catch {
    return [];
  }
}
