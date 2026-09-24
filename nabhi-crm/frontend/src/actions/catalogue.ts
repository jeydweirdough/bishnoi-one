"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { BundleRow, CatalogueProduct, PromoRow, SalesRules } from "@/src/platform/lib/types";

// The catalogue: products, promos, bundles and the pricing rules. The API
// checks the person's role on every one of these and logs each change.

export type ProductInput = {
  code: string;
  name: string;
  genericName: string | null;
  strength: string | null;
  form: string | null;
  unit: string;
  isActive: boolean;
  /** price type code -> centavos; null clears that price. */
  prices: Record<string, number | null>;
  /** Added fields (Settings → Forms), by key: only what changed (null clears one). */
  extra?: Record<string, string | boolean | string[] | null>;
};

export async function saveProduct(id: string | null, input: ProductInput): Promise<Result<CatalogueProduct>> {
  return attempt(async () => {
    const saved = id ? await api.patch<CatalogueProduct>(`/products/${enc(id)}`, input) : await api.post<CatalogueProduct>("/products", input);
    refresh();
    return saved;
  });
}

export async function deleteProduct(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/products/${enc(id)}`);
    refresh();
    return null;
  });
}

export type PromoInput = Omit<PromoRow, "id" | "state">;

export async function savePromo(id: string | null, input: PromoInput): Promise<Result<PromoRow>> {
  return attempt(async () => {
    const saved = id ? await api.put<PromoRow>(`/promos/${enc(id)}`, input) : await api.post<PromoRow>("/promos", input);
    refresh();
    return saved;
  });
}

export async function deletePromo(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/promos/${enc(id)}`);
    refresh();
    return null;
  });
}

export type BundleInput = Omit<BundleRow, "id" | "state">;

export async function saveBundle(id: string | null, input: BundleInput): Promise<Result<BundleRow>> {
  return attempt(async () => {
    const saved = id ? await api.put<BundleRow>(`/bundles/${enc(id)}`, input) : await api.post<BundleRow>("/bundles", input);
    refresh();
    return saved;
  });
}

export async function deleteBundle(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/bundles/${enc(id)}`);
    refresh();
    return null;
  });
}

type PriceTypeInput = Partial<Omit<SalesRules["priceTypes"][number], "code">> & { code?: string };

/** A new price type (with a code), or a change to one (by its code). */
export async function savePriceType(code: string | null, input: PriceTypeInput): Promise<Result<SalesRules>> {
  return attempt(async () => {
    const rules = code
      ? await api.patch<SalesRules>(`/pricing/price-types/${enc(code)}`, input)
      : await api.post<SalesRules>("/pricing/price-types", input);
    refresh();
    return rules;
  });
}

export async function saveIssuer(code: string | null, input: { code?: string; name?: string; isActive?: boolean }): Promise<Result<SalesRules>> {
  return attempt(async () => {
    const rules = code ? await api.patch<SalesRules>(`/pricing/issuers/${enc(code)}`, input) : await api.post<SalesRules>("/pricing/issuers", input);
    refresh();
    return rules;
  });
}

export async function saveSalesSettings(input: Partial<SalesRules["settings"]>): Promise<Result<SalesRules>> {
  return attempt(async () => {
    const rules = await api.patch<SalesRules>("/pricing/settings", input);
    refresh();
    return rules;
  });
}
