"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

// Everything the screens change. The API checks the caller's role and every
// rule on each one (enough stock, the right status, nobody locked out);
// these only carry the request and hand back what it said.

type Json = Record<string, unknown>;

async function send<T = Json>(method: "post" | "put" | "patch" | "del", path: string, body?: unknown): Promise<Result<T>> {
  return attempt(async () => {
    const out = method === "del" ? await api.del<T>(path) : await api[method]<T>(path, body ?? {});
    refresh();
    return out;
  });
}

type Id = { id: string };
type Numbered = { id: string; number: string };

// --- catalog ---------------------------------------------------------------------------

export async function saveProduct(id: string | null, input: Json): Promise<Result<Id>> {
  return id ? send<Id>("patch", `/inventory/products/${enc(id)}`, input) : send<Id>("post", "/inventory/products", input);
}
export async function deleteProduct(id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/products/${enc(id)}`);
}
export async function uploadImage(id: string, form: FormData): Promise<Result<Id>> {
  return attempt(async () => {
    const out = await api.upload<Id>(`/inventory/products/${enc(id)}/images`, form);
    refresh();
    return out;
  });
}
export async function deleteImage(productId: string, imageId: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/products/${enc(productId)}/images/${enc(imageId)}`);
}
export async function setSupplierPrice(productId: string, supplierId: string, input: Json): Promise<Result> {
  return send("put", `/inventory/products/${enc(productId)}/suppliers/${enc(supplierId)}`, input);
}
export async function removeSupplierPrice(productId: string, supplierId: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/products/${enc(productId)}/suppliers/${enc(supplierId)}`);
}

type CatalogList = "categories" | "brands" | "units";
export async function saveCatalogItem(list: CatalogList, key: string | null, input: Json): Promise<Result> {
  return key ? send("patch", `/inventory/${list}/${enc(key)}`, input) : send("post", `/inventory/${list}`, input);
}
export async function deleteCatalogItem(list: CatalogList, key: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/${list}/${enc(key)}`);
}

// --- warehouses -------------------------------------------------------------------------

export async function saveWarehouse(id: string | null, input: Json): Promise<Result<Id>> {
  return id ? send<Id>("patch", `/inventory/warehouses/${enc(id)}`, input) : send<Id>("post", "/inventory/warehouses", input);
}
export async function deleteWarehouse(id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/warehouses/${enc(id)}`);
}
export async function saveLocation(warehouseId: string, id: string | null, input: Json): Promise<Result<Id>> {
  const base = `/inventory/warehouses/${enc(warehouseId)}/locations`;
  return id ? send<Id>("patch", `${base}/${enc(id)}`, input) : send<Id>("post", base, input);
}
export async function deleteLocation(warehouseId: string, id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/warehouses/${enc(warehouseId)}/locations/${enc(id)}`);
}

// --- suppliers and purchasing -----------------------------------------------------------

export async function saveSupplier(id: string | null, input: Json): Promise<Result<Id>> {
  return id ? send<Id>("patch", `/inventory/suppliers/${enc(id)}`, input) : send<Id>("post", "/inventory/suppliers", input);
}
export async function deleteSupplier(id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/suppliers/${enc(id)}`);
}
export async function savePurchaseOrder(id: string | null, input: Json): Promise<Result<Id>> {
  return id ? send<Id>("put", `/inventory/purchase-orders/${enc(id)}`, input) : send<Numbered>("post", "/inventory/purchase-orders", input);
}
export async function setPurchaseOrderDates(id: string, input: Json): Promise<Result> {
  return send("patch", `/inventory/purchase-orders/${enc(id)}`, input);
}
export async function purchaseOrderStep(id: string, step: "place" | "cancel"): Promise<Result> {
  return send("post", `/inventory/purchase-orders/${enc(id)}/${step}`);
}
export async function deletePurchaseOrder(id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/purchase-orders/${enc(id)}`);
}
export async function receiveDelivery(input: Json): Promise<Result<Numbered & { orderStatus: string | null }>> {
  return send("post", "/inventory/receipts", input);
}

// --- orders -----------------------------------------------------------------------------

export async function saveOrder(id: string | null, input: Json): Promise<Result<Id>> {
  return id ? send<Id>("put", `/inventory/orders/${enc(id)}`, input) : send<Numbered>("post", "/inventory/orders", input);
}
export async function orderStep(id: string, step: "confirm" | "pick" | "cancel"): Promise<Result> {
  return send("post", `/inventory/orders/${enc(id)}/${step}`);
}
export async function issueOrder(id: string, input: Json): Promise<Result> {
  return send("post", `/inventory/orders/${enc(id)}/issue`, input);
}
export async function deleteOrder(id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/orders/${enc(id)}`);
}

// --- transfers --------------------------------------------------------------------------

export async function saveTransfer(id: string | null, input: Json): Promise<Result<Id>> {
  return id ? send<Id>("put", `/inventory/transfers/${enc(id)}`, input) : send<Numbered>("post", "/inventory/transfers", input);
}
export async function transferStep(id: string, step: "request" | "approve" | "cancel"): Promise<Result> {
  return send("post", `/inventory/transfers/${enc(id)}/${step}`);
}
export async function dispatchTransfer(id: string, input: Json): Promise<Result> {
  return send("post", `/inventory/transfers/${enc(id)}/dispatch`, input);
}
export async function receiveTransfer(id: string, input: Json): Promise<Result> {
  return send("post", `/inventory/transfers/${enc(id)}/receive`, input);
}
export async function deleteTransfer(id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/transfers/${enc(id)}`);
}

// --- adjustments and counts -------------------------------------------------------------

export async function createAdjustment(input: Json): Promise<Result<Numbered & { status: string }>> {
  return send("post", "/inventory/adjustments", input);
}
export async function adjustmentStep(id: string, step: "approve" | "reject"): Promise<Result> {
  return send("post", `/inventory/adjustments/${enc(id)}/${step}`);
}
export async function withdrawAdjustment(id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/adjustments/${enc(id)}`);
}
export async function startCount(input: Json): Promise<Result<Numbered>> {
  return send("post", "/inventory/counts", input);
}
export async function recordCounts(id: string, lines: { lineId: string; counted: number | null }[]): Promise<Result> {
  return send("put", `/inventory/counts/${enc(id)}/lines`, { lines });
}
export async function addCountLine(id: string, input: Json): Promise<Result<Id>> {
  return send("post", `/inventory/counts/${enc(id)}/lines`, input);
}
export async function countStep(id: string, step: "submit" | "reopen" | "approve" | "cancel"): Promise<Result<{ adjustmentId?: string | null }>> {
  return send("post", `/inventory/counts/${enc(id)}/${step}`);
}

// --- administration ---------------------------------------------------------------------

export async function saveUser(id: string | null, input: Json): Promise<Result> {
  return id ? send("patch", `/admin/users/${enc(id)}`, input) : send("post", "/admin/users", input);
}
export async function setUserPassword(id: string, password: string): Promise<Result> {
  return attempt(async () => {
    await api.post(`/admin/users/${enc(id)}/password`, { password });
    return {};
  });
}
export async function saveRole(id: string | null, input: Json): Promise<Result<Id & { name: string }>> {
  return id ? send("patch", `/admin/roles/${enc(id)}`, input) : send("post", "/admin/roles", input);
}
export async function deleteRole(id: string): Promise<Result<null>> {
  return send<null>("del", `/admin/roles/${enc(id)}`);
}
