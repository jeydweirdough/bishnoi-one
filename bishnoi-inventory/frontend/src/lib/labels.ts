import type { Me } from "@/src/platform/lib/types";
import type { AdjustmentBrief, CountStatus, MovementKind, OrderKind, OrderStatus, POStatus, ProductStatus, ProductType, StockState, TransferStatus } from "./types";

/** Whether the person's role allows this ("stock.view", "adjustments.approve"). The API checks again. */
export const can = (me: Me, permission: string): boolean => me.permissions?.includes(permission) ?? false;

export const MOVEMENT_KINDS: Record<MovementKind, string> = {
  receive: "Stock received",
  issue: "Stock out",
  transfer_out: "Transferred out",
  transfer_in: "Transferred in",
  adjust: "Adjustment",
  return_in: "Customer return",
  return_out: "Returned to supplier",
  damage: "Marked damaged",
  write_off: "Written off",
  expired: "Expired",
  lost: "Lost",
  reserve: "Reserved",
  release: "Released",
};

/** The kinds people filter the trail by, grouped the way they think of them. */
export const MOVEMENT_FILTERS: { key: string; label: string }[] = [
  { key: "", label: "All" },
  { key: "receive,return_in", label: "Stock in" },
  { key: "issue,return_out", label: "Stock out" },
  { key: "transfer_out,transfer_in", label: "Transfers" },
  { key: "adjust", label: "Adjustments" },
  { key: "damage,write_off,expired,lost", label: "Damage, expiry and loss" },
  { key: "reserve,release", label: "Reservations" },
];

export const PO_STATUSES: Record<POStatus, string> = {
  draft: "Draft",
  ordered: "Ordered",
  partial: "Partially received",
  received: "Received",
  cancelled: "Cancelled",
};

export const ORDER_STATUSES: Record<OrderStatus, string> = {
  draft: "Draft",
  confirmed: "Reserved",
  picking: "Picking",
  issued: "Issued",
  cancelled: "Cancelled",
};

export const ORDER_KINDS: Record<OrderKind, string> = {
  sale: "Customer order",
  internal: "Internal use",
  department: "Department request",
  project: "Project",
  distribution: "Distribution",
};

export const TRANSFER_STATUSES: Record<TransferStatus, string> = {
  draft: "Draft",
  requested: "Requested",
  approved: "Approved",
  in_transit: "In transit",
  received: "Received",
  cancelled: "Cancelled",
};

export const ADJUSTMENT_STATUSES: Record<AdjustmentBrief["status"], string> = {
  pending: "Pending approval",
  posted: "Posted",
  rejected: "Rejected",
};

export const COUNT_STATUSES: Record<CountStatus, string> = {
  open: "Counting",
  submitted: "Pending approval",
  approved: "Approved",
  cancelled: "Cancelled",
};

export const PRODUCT_TYPES: Record<ProductType, string> = {
  stock: "Stock item",
  consumable: "Consumable",
  asset: "Asset or equipment",
  service: "Service (non-stock)",
};

export const PRODUCT_STATUSES: Record<ProductStatus, string> = {
  active: "Active",
  inactive: "Inactive",
  discontinued: "Discontinued",
};

export const STOCK_STATES: Record<Exclude<StockState, null>, string> = {
  out: "Out of stock",
  low: "Low",
  over: "Over maximum",
  ok: "In stock",
};

/** +500, -3, 0: a change in stock, always signed. */
export function signed(n: number, count: (n: number) => string = String): string {
  return n > 0 ? `+${count(n)}` : n < 0 ? `−${count(-n)}` : "0";
}

/** Where a movement's reference leads. */
export function referenceHref(type: string | null, id: string | null): string | null {
  if (!type || !id) return null;
  const base: Record<string, string> = {
    receipt: "/receipts",
    order: "/orders",
    transfer: "/transfers",
    adjustment: "/adjustments",
    count: "/counts",
    purchase_order: "/purchase-orders",
  };
  return base[type] ? `${base[type]}/${id}` : null;
}

/** A query string from the values that are set. */
export function query(values: Record<string, string | number | boolean | null | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(values)) if (v !== null && v !== undefined && v !== "" && v !== false) q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}

/** One value of a page's search parameters. */
export function param(search: Record<string, string | string[] | undefined>, key: string): string {
  const v = search[key];
  return typeof v === "string" ? v.trim() : "";
}
