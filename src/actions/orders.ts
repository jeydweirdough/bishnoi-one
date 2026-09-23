"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { OrderField, OrderListKind, OrderSettings } from "@/src/platform/lib/types";

// Settings -> Orders. The API checks that the caller manages settings.

export type OrderListItemInput = { code?: string; name: string; isActive: boolean };
export type OrderFieldInput = Omit<OrderField, "key"> & { key?: string };

export async function saveOrderList(kind: OrderListKind, items: OrderListItemInput[]): Promise<Result> {
  return attempt(async () => {
    await api.put<OrderSettings>(`/admin/orders/lists/${enc(kind)}`, { items });
    refresh();
    return null;
  });
}

export async function saveOrderFields(fields: OrderFieldInput[]): Promise<Result> {
  return attempt(async () => {
    await api.put<OrderSettings>("/admin/orders/fields", { fields });
    refresh();
    return null;
  });
}

export async function saveOrderRules(rules: { largeOrderCentavos: number; recycleDays: number; orderPrefix: string }): Promise<Result> {
  return attempt(async () => {
    await api.put<OrderSettings>("/admin/orders/rules", rules);
    refresh();
    return null;
  });
}
