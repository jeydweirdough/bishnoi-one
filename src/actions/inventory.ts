"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Bundle, Product, Promo, PromoKind, PromoTier } from "@/src/platform/lib/types";

// Products, prices and promos. The API checks the caller's Inventory access on every one.

export type ProductInput = {
  code: string;
  name: string;
  genericName: string | null;
  strength: string | null;
  form: string | null;
  unit: string;
};

export async function createProduct(input: ProductInput & { prices: Record<string, number> }): Promise<Result<{ id: string }>> {
  return attempt(async () => {
    const product = await api.post<Product>("/inventory/products", input);
    return { id: product.id };
  });
}

/** Details and prices together, as the product page saves them. */
export async function updateProduct(
  id: string,
  input: ProductInput,
  prices: Record<string, number | null>,
): Promise<Result> {
  return attempt(async () => {
    await api.patch<Product>(`/inventory/products/${enc(id)}`, input);
    await api.put<Product>(`/inventory/products/${enc(id)}/prices`, { prices });
    refresh();
    return null;
  });
}

export async function setProductActive(id: string, isActive: boolean): Promise<Result> {
  return attempt(async () => {
    await api.patch<Product>(`/inventory/products/${enc(id)}`, { isActive });
    refresh();
    return null;
  });
}

export type PromoInput = {
  name: string;
  kind: PromoKind;
  percentBp: number | null;
  amountCentavos: number | null;
  buyQty: number | null;
  freeQty: number | null;
  tiers: PromoTier[];
  startsOn: string;
  endsOn: string | null;
  productIds: string[] | null;
  divisionCodes: string[];
};

export async function createPromo(input: PromoInput): Promise<Result<{ id: string }>> {
  return attempt(async () => {
    const promo = await api.post<Promo>("/inventory/promos", input);
    return { id: promo.id };
  });
}

export async function updatePromo(id: string, input: PromoInput): Promise<Result> {
  return attempt(async () => {
    await api.put<Promo>(`/inventory/promos/${enc(id)}`, input);
    refresh();
    return null;
  });
}

export async function setPromoActive(id: string, isActive: boolean): Promise<Result> {
  return attempt(async () => {
    await api.patch<Promo>(`/inventory/promos/${enc(id)}`, { isActive });
    refresh();
    return null;
  });
}

export type BundleInput = {
  code: string;
  name: string;
  priceCentavos: number;
  asOneLine: boolean;
  items: { productId: string; qty: number }[];
  startsOn: string;
  endsOn: string | null;
  divisionCodes: string[];
};

export async function createBundle(input: BundleInput): Promise<Result<{ id: string }>> {
  return attempt(async () => {
    const bundle = await api.post<Bundle>("/inventory/bundles", input);
    return { id: bundle.id };
  });
}

export async function updateBundle(id: string, input: BundleInput): Promise<Result> {
  return attempt(async () => {
    await api.put<Bundle>(`/inventory/bundles/${enc(id)}`, input);
    refresh();
    return null;
  });
}

export async function setBundleActive(id: string, isActive: boolean): Promise<Result> {
  return attempt(async () => {
    await api.patch<Bundle>(`/inventory/bundles/${enc(id)}`, { isActive });
    refresh();
    return null;
  });
}
