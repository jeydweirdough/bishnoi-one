"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/inventory/platform/lib/api";
import { attempt, type Result } from "@/src/modules/inventory/platform/lib/result";
import { apiFor } from "@/src/platform/lib/api";
import type { QuoteFor, QuoteInput } from "@/src/modules/crm/actions/customers";
import type { QuotePreview } from "@/src/platform/lib/types";

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

// A sales order made directly with the quote form (2026-11-23): priced by the CRM exactly as a quote, then made in
// Inventory. These pages sit in the CRM frame but talk to Inventory, so the CRM is named here.

export async function previewForOrder(to: QuoteFor, input: QuoteInput): Promise<Result<QuotePreview>> {
  return attempt(() => apiFor("crm").post<QuotePreview>(`/${to.kind}/${enc(to.id)}/quotes/preview`, { ...input, letter: null }));
}

/** `form` carries the order as JSON in "order" and, when a guarantee letter pays, the letter in "letterFile". */
export async function createDirectOrder(to: QuoteFor, form: FormData): Promise<Result<{ id: string; number: string }>> {
  const body = new FormData();
  body.set("order", String(form.get("order") ?? ""));
  const letter = form.get("letterFile");
  if (letter instanceof File && letter.size > 0) body.set("letterFile", letter, letter.name);
  return attempt(async () => {
    const made = await apiFor("crm").upload<{ id: string; number: string }>(`/${to.kind}/${enc(to.id)}/sales-orders`, body);
    refresh();
    return made;
  });
}
