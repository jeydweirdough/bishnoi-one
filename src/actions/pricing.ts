"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { DivisionPricing, PriceEntry, PricingRules } from "@/src/platform/lib/types";

// Settings -> Pricing rules. The API checks that the caller manages settings on every one.

export type DivisionRulesInput = Omit<DivisionPricing, "code" | "name">;

export async function saveDivisionRules(divisions: Record<string, DivisionRulesInput>): Promise<Result<PricingRules>> {
  return attempt(async () => {
    const saved = await api.put<PricingRules>("/admin/pricing/divisions", { divisions });
    refresh();
    return saved;
  });
}

export async function addPriceType(input: {
  name: string;
  entry: PriceEntry;
  requiresNotes: boolean;
  needsApproval: boolean;
}): Promise<Result> {
  return attempt(async () => {
    await api.post<PricingRules>("/admin/pricing/price-types", input);
    refresh();
    return null;
  });
}

export async function updatePriceType(
  code: string,
  input: { name?: string; entry?: PriceEntry; requiresNotes?: boolean; needsApproval?: boolean; isActive?: boolean },
): Promise<Result> {
  return attempt(async () => {
    await api.patch<PricingRules>(`/admin/pricing/price-types/${enc(code)}`, input);
    refresh();
    return null;
  });
}

export async function addIssuer(name: string): Promise<Result> {
  return attempt(async () => {
    await api.post<PricingRules>("/admin/pricing/issuers", { name });
    refresh();
    return null;
  });
}

export async function updateIssuer(code: string, input: { name?: string; isActive?: boolean }): Promise<Result> {
  return attempt(async () => {
    await api.patch<PricingRules>(`/admin/pricing/issuers/${enc(code)}`, input);
    refresh();
    return null;
  });
}

/** Which way a newly added bundle starts. A default, not a rule: bundles that
 *  already exist keep the way they were set up. */
export async function saveSellingDefaults(input: { bundlesAsOneLine: boolean }): Promise<Result<PricingRules>> {
  return attempt(async () => {
    const saved = await api.put<PricingRules>("/admin/pricing/defaults", input);
    refresh();
    return saved;
  });
}
