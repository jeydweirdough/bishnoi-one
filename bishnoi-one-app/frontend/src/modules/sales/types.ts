// The Sales app's sales orders, as the Operations service gives them (app/routers/sales.py).

export type SalesStatus = "draft" | "pending" | "confirmed" | "delivered" | "rejected" | "cancelled";

export type SalesOrderBrief = {
  id: string;
  number: string;
  status: SalesStatus;
  statusLabel: string;
  customer: { id: string | null; name: string; address: string | null; tin: string | null };
  quote: { id: string; number: string | null } | null;
  salesperson: { id: string | null; name: string } | null;
  division: string | null;
  team: string | null;
  warehouse: { id: string; code: string; name: string };
  scheduledOn: string | null;
  totalCentavos: number;
  currency: string;
  units: number;
  createdAt: string;
  createdBy: string | null;
};

export type SalesOrder = SalesOrderBrief & {
  /** The vendor ships it straight to the customer (15c); the purchase orders it raised (15b, 15c). */
  dropship?: boolean;
  purchaseOrders?: { id: string; number: string; status: string; dropship: boolean; supplier: string | null }[];
  /** Invoiced from its delivery by Finance, and paid (step 13). */
  invoice?: { id: string; number: string | null; invoicedAt: string | null; total: number | null; paidAt: string | null } | null;
  payer: { kind: string; issuer?: string; letterNumber?: string; amountCentavos?: number } | null;
  notes: string | null;
  grossCentavos: number;
  discountCentavos: number;
  decidedBy: { id: string; name: string } | null;
  decidedAt: string | null;
  decisionNote: string | null;
  deliveredAt: string | null;
  lines: { id: string; product: { id: string; sku: string; name: string; unit: string }; quantity: number; freeQuantity: number; unitPrice: number; discount: number; total: number; delivered: number }[];
  deliveries: { id: string; number: string; status: string; issuedAt: string | null; shipping?: import("@/src/modules/inventory/lib/types").Shipping | null }[];
};
