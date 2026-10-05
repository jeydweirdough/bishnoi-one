"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { ConditionKind, PriceRules, Procedure } from "../components/catalogue/price-rules-types";

// Price rules: the order a quote line is priced in, price groups, and dated
// rules. The API checks products.edit and every rule; these carry the request.

export async function saveProcedure(input: Procedure & { pricesIncludeTax: boolean }): Promise<Result<PriceRules>> {
  return attempt(async () => {
    const rules = await api.put<PriceRules>("/pricing/procedure", input);
    refresh();
    return rules;
  });
}

export async function addPriceGroup(input: { code: string; name: string }): Promise<Result<PriceRules>> {
  return attempt(async () => {
    const rules = await api.post<PriceRules>("/pricing/groups", input);
    refresh();
    return rules;
  });
}

export async function updatePriceGroup(code: string, change: { name?: string; isActive?: boolean }): Promise<Result<PriceRules>> {
  return attempt(async () => {
    const rules = await api.patch<PriceRules>(`/pricing/groups/${enc(code)}`, change);
    refresh();
    return rules;
  });
}

export async function deletePriceGroup(code: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/pricing/groups/${enc(code)}`);
    refresh();
    return null;
  });
}

export type RuleInput = {
  kind: ConditionKind;
  name: string;
  productId: string | null;
  priceGroupCode: string | null;
  priceTypeCode: string | null;
  amountCentavos: number | null;
  percentBp: number | null;
  tiers: { minQty: number; percentBp: number }[];
  startsOn: string | null;
  endsOn: string | null;
  isActive: boolean;
};

export async function saveRule(id: string | null, input: RuleInput): Promise<Result<PriceRules>> {
  return attempt(async () => {
    const rules = id ? await api.put<PriceRules>(`/pricing/conditions/${enc(id)}`, input) : await api.post<PriceRules>("/pricing/conditions", input);
    refresh();
    return rules;
  });
}

export async function deleteRule(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/pricing/conditions/${enc(id)}`);
    refresh();
    return null;
  });
}
