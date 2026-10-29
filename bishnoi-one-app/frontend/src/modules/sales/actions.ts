"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/inventory/platform/lib/api";
import { attempt, type Result } from "@/src/modules/inventory/platform/lib/result";

// The Sales app's sales orders (feature plan step 11), on the Operations service (/inventory/sales-orders).

type Json = Record<string, unknown>;

async function send<T = Json>(method: "post" | "put", path: string, body?: unknown): Promise<Result<T>> {
  return attempt(async () => {
    const out = method === "put" ? await api.put<T>(path, body ?? {}) : await api.post<T>(path, body ?? {});
    refresh();
    return out;
  });
}

export async function saveSalesOrder(id: string | null, input: Json): Promise<Result<{ id: string; number?: string }>> {
  return id ? send("put", `/inventory/sales-orders/${enc(id)}`, input) : send("post", "/inventory/sales-orders", input);
}

export async function salesOrderStep(id: string, step: "submit" | "approve" | "cancel"): Promise<Result<unknown>> {
  return send("post", `/inventory/sales-orders/${enc(id)}/${step}`);
}

export async function rejectSalesOrder(id: string, note: string): Promise<Result<unknown>> {
  return send("post", `/inventory/sales-orders/${enc(id)}/reject`, { note });
}
