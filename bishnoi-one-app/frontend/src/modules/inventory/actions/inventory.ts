"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/inventory/platform/lib/api";
import { attempt, type Result } from "@/src/modules/inventory/platform/lib/result";

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
export type CprLine = { sku: string; cprNumber: string | null; validUntil: string | null };
export type CprCheck = {
  rows: { line: number; sku: string; product?: { id: string; sku: string; name: string }; cprNumber: string | null; validUntil: string | null; problems: string[]; changes: string[]; result: "change" | "same" | "problem" }[];
  changes: number;
  same: number;
  problems: number;
  saved: number;
};
/** Many products' CPR numbers at once: checked only, or (apply) the right rows saved. */
export async function importCpr(rows: CprLine[], apply: boolean): Promise<Result<CprCheck>> {
  return apply ? send<CprCheck>("post", "/inventory/products/cpr", { rows, apply }) : attempt(() => api.post<CprCheck>("/inventory/products/cpr", { rows, apply }));
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
export async function setSupplierPrice(productId: string, supplierId: string, input: Json): Promise<Result<unknown>> {
  return send("put", `/inventory/products/${enc(productId)}/suppliers/${enc(supplierId)}`, input);
}
export async function removeSupplierPrice(productId: string, supplierId: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/products/${enc(productId)}/suppliers/${enc(supplierId)}`);
}

type CatalogList = "categories" | "brands" | "units";
export async function saveCatalogItem(list: CatalogList, key: string | null, input: Json): Promise<Result<unknown>> {
  return key ? send("patch", `/inventory/${list}/${enc(key)}`, input) : send("post", `/inventory/${list}`, input);
}
/** Deletes one; with `moveTo`, what still uses it (products, categories inside it) moves there first. */
export async function deleteCatalogItem(list: CatalogList, key: string, moveTo?: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/${list}/${enc(key)}${moveTo ? `?moveTo=${enc(moveTo)}` : ""}`);
}

// --- warehouses -------------------------------------------------------------------------

export async function saveWarehouse(id: string | null, input: Json): Promise<Result<Id>> {
  return id ? send<Id>("patch", `/inventory/warehouses/${enc(id)}`, input) : send<Id>("post", "/inventory/warehouses", input);
}
// Order-on-demand, dropshipping, consignment and documents with products (steps 15b–15e).
export async function sendSaleDocuments(kind: "orders" | "sales-orders", id: string, to: string[], message: string | null): Promise<Result<{ sent: number; to: string[] }>> {
  return send<{ sent: number; to: string[] }>("post", `/inventory/${kind}/${enc(id)}/documents/send`, { to, message });
}
export async function settleConsignment(supplierId: string): Promise<Result<{ id: string; number: string; total: number }>> {
  return send<{ id: string; number: string; total: number }>("post", `/inventory/consignment/${enc(supplierId)}/settle`, {});
}
export async function setDropship(orderId: string, dropship: boolean): Promise<Result<unknown>> {
  return send("put", `/inventory/sales-orders/${enc(orderId)}/dropship`, { dropship });
}
export async function dropshipDelivered(poId: string): Promise<Result<unknown>> {
  return send("post", `/inventory/purchase-orders/${enc(poId)}/dropship-delivered`, {});
}
export async function uploadProductDocument(productId: string, form: FormData): Promise<Result<unknown>> {
  return attempt(async () => {
    const out = await api.upload<unknown>(`/inventory/products/${enc(productId)}/documents`, form);
    refresh();
    return out;
  });
}
export async function saveProductDocument(productId: string, id: string, input: Json): Promise<Result<unknown>> {
  return send("patch", `/inventory/products/${enc(productId)}/documents/${enc(id)}`, input);
}
export async function deleteProductDocument(productId: string, id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/products/${enc(productId)}/documents/${enc(id)}`);
}

// Replenishment (step 15a).
export async function makeReplenishmentDrafts(warehouseId: string): Promise<Result<{ made: { id: string; number: string; supplier: string | null; lines: number }[]; needVendor: { id: string; name: string }[] }>> {
  return send("post", "/inventory/replenishment/drafts", { warehouseId });
}
export async function saveReplenishmentSettings(input: Json): Promise<Result<unknown>> {
  return send("put", "/inventory/replenishment/settings", input);
}

// An item's packs (step 14e).
export async function savePackaging(productId: string, id: string | null, input: Json): Promise<Result<unknown>> {
  return id
    ? send("patch", `/inventory/products/${enc(productId)}/packagings/${enc(id)}`, input)
    : send("post", `/inventory/products/${enc(productId)}/packagings`, input);
}
export async function deletePackaging(productId: string, id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/products/${enc(productId)}/packagings/${enc(id)}`);
}

// Packages and waves (step 14d).
export async function packDelivery(orderId: string, input: Json): Promise<Result<unknown>> {
  return send("post", `/inventory/orders/${enc(orderId)}/packages`, input);
}
export async function unpackDelivery(orderId: string, packageId: string): Promise<Result<unknown>> {
  return send("del", `/inventory/orders/${enc(orderId)}/packages/${enc(packageId)}`);
}
export async function makeWave(orderIds: string[]): Promise<Result<{ id: string; number: string }>> {
  return send<{ id: string; number: string }>("post", "/inventory/waves", { orderIds });
}
export async function waveStep(id: string, step: "done" | "remove", orderId?: string): Promise<Result<unknown>> {
  return send("post", `/inventory/waves/${enc(id)}/${step}`, orderId ? { orderId } : {});
}
export async function deleteWave(id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/waves/${enc(id)}`);
}

// Scanning (step 14c).
export type Scanned = {
  kind: "product" | "batch" | "serial" | "document" | "batches" | "unknown";
  code: string;
  href?: string;
  product?: { id: string; sku: string; name: string };
  batch?: { id: string; batchNo: string; expiresOn: string | null };
  serial?: string;
  document?: { id: string; number: string; label: string };
  batches?: { id: string; batchNo: string; product: { id: string; name: string } }[];
  /** A pack's own barcode (step 14e): how many of the item it holds. */
  pack?: { name: string; quantity: number };
};
export async function scanCode(code: string): Promise<Result<Scanned>> {
  return attempt(() => api.get<Scanned>(`/inventory/scan?code=${enc(code)}`));
}
export async function countScan(countId: string, code: string, quantity = 1): Promise<Result<{ lineId: string; product: { id: string; name: string }; batch: { batchNo: string } | null; counted: number; expected: number; new: boolean }>> {
  return send("post", `/inventory/counts/${enc(countId)}/scan`, { code, quantity });
}

// Scheduled cycle counts (step 14b).
export async function saveCountSchedule(id: string | null, input: Json): Promise<Result<unknown>> {
  return id ? send("patch", `/inventory/count-schedules/${enc(id)}`, input) : send("post", "/inventory/count-schedules", input);
}
export async function deleteCountSchedule(id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/count-schedules/${enc(id)}`);
}
export async function startScheduledCount(id: string): Promise<Result<{ id: string; number: string }>> {
  return send<{ id: string; number: string }>("post", `/inventory/count-schedules/${enc(id)}/start`, {});
}
/** A receipt's quality check, done (step 14a). */
export async function finishQualityCheck(id: string, input: Json): Promise<Result<unknown>> {
  return send("post", `/inventory/quality-checks/${enc(id)}/done`, input);
}
/** Finds a warehouse's pin on the map from its address, and keeps it. */
export async function locateWarehouse(id: string): Promise<Result<Id & { latitude: number; longitude: number }>> {
  return send("post", `/inventory/warehouses/${enc(id)}/locate`);
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
export async function setPurchaseOrderDates(id: string, input: Json): Promise<Result<unknown>> {
  return send("patch", `/inventory/purchase-orders/${enc(id)}`, input);
}
export async function purchaseOrderStep(id: string, step: "place" | "cancel"): Promise<Result<unknown>> {
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
export async function orderStep(id: string, step: "confirm" | "pick" | "cancel"): Promise<Result<unknown>> {
  return send("post", `/inventory/orders/${enc(id)}/${step}`);
}
export async function issueOrder(id: string, input: Json): Promise<Result<unknown>> {
  return send("post", `/inventory/orders/${enc(id)}/issue`, input);
}
/** The customer signs for what they received (proof of delivery, step 10). */
export async function signForDelivery(id: string, name: string, signature: string): Promise<Result<unknown>> {
  return send("post", `/inventory/orders/${enc(id)}/received`, { name, signature });
}
// Shipping with couriers (step 12).
export async function setShipping(id: string, input: { method: string; courierId: string | null; trackingNumber: string | null; fee: number; feeCharged: boolean }): Promise<Result<unknown>> {
  return send("put", `/inventory/orders/${enc(id)}/shipping`, input);
}
export async function markDelivered(id: string, receivedBy: string, photo: string | null): Promise<Result<unknown>> {
  return send("post", `/inventory/orders/${enc(id)}/delivered`, { receivedBy, photo });
}
export async function markFailed(id: string, reason: string): Promise<Result<unknown>> {
  return send("post", `/inventory/orders/${enc(id)}/failed`, { reason });
}
export async function sendAgain(id: string): Promise<Result<unknown>> {
  return send("post", `/inventory/orders/${enc(id)}/send-again`, {});
}
export async function saveCourier(id: string | null, input: Json): Promise<Result<unknown>> {
  return id ? send("patch", `/inventory/couriers/${enc(id)}`, input) : send("post", "/inventory/couriers", input);
}
export async function deleteOrder(id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/orders/${enc(id)}`);
}

// --- transfers --------------------------------------------------------------------------

export async function saveTransfer(id: string | null, input: Json): Promise<Result<Id>> {
  return id ? send<Id>("put", `/inventory/transfers/${enc(id)}`, input) : send<Numbered>("post", "/inventory/transfers", input);
}
export async function transferStep(id: string, step: "request" | "approve" | "cancel"): Promise<Result<unknown>> {
  return send("post", `/inventory/transfers/${enc(id)}/${step}`);
}
export async function dispatchTransfer(id: string, input: Json): Promise<Result<unknown>> {
  return send("post", `/inventory/transfers/${enc(id)}/dispatch`, input);
}
export async function receiveTransfer(id: string, input: Json): Promise<Result<unknown>> {
  return send("post", `/inventory/transfers/${enc(id)}/receive`, input);
}
export async function deleteTransfer(id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/transfers/${enc(id)}`);
}

// --- adjustments and counts -------------------------------------------------------------

export async function createAdjustment(input: Json): Promise<Result<Numbered & { status: string }>> {
  return send("post", "/inventory/adjustments", input);
}
export async function adjustmentStep(id: string, step: "approve" | "reject"): Promise<Result<unknown>> {
  return send("post", `/inventory/adjustments/${enc(id)}/${step}`);
}
export async function withdrawAdjustment(id: string): Promise<Result<null>> {
  return send<null>("del", `/inventory/adjustments/${enc(id)}`);
}
export async function startCount(input: Json): Promise<Result<Numbered>> {
  return send("post", "/inventory/counts", input);
}
export async function recordCounts(id: string, lines: { lineId: string; counted: number | null }[]): Promise<Result<unknown>> {
  return send("put", `/inventory/counts/${enc(id)}/lines`, { lines });
}
export async function addCountLine(id: string, input: Json): Promise<Result<Id>> {
  return send("post", `/inventory/counts/${enc(id)}/lines`, input);
}
export async function countStep(id: string, step: "submit" | "reopen" | "approve" | "cancel"): Promise<Result<{ adjustmentId?: string | null }>> {
  return send("post", `/inventory/counts/${enc(id)}/${step}`);
}

// --- administration ---------------------------------------------------------------------

export async function saveUser(id: string | null, input: Json): Promise<Result<unknown>> {
  return id ? send("patch", `/admin/users/${enc(id)}`, input) : send("post", "/admin/users", input);
}
export async function setUserPassword(id: string, password: string): Promise<Result<unknown>> {
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
