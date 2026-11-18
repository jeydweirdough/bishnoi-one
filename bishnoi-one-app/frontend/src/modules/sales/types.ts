// The Sales app's sales orders, as the Operations service gives them (app/routers/sales.py).

export type SalesStatus = "draft" | "pending" | "confirmed" | "delivered" | "rejected" | "cancelled";

export type SalesOrderBrief = {
  id: string;
  number: string;
  status: SalesStatus;
  statusLabel: string;
  /** Once invoiced, the invoice is the order's source of truth (Step 4D): its state, and where the amounts come from. */
  invoiceState?: "issued" | "paid" | "voided" | null;
  amountsFrom?: "invoice" | "order";
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
  /** The purchase orders it raised for what the warehouse lacked (order-on-demand, 15b). */
  purchaseOrders?: { id: string; number: string; status: string; supplier: string | null }[];
  /** Invoiced from its delivery by Finance, and paid (step 13). */
  invoice?: {
    id: string; number: string | null; invoicedAt: string | null; total: number | null; paidAt: string | null;
    /** The invoice's figures as Finance issued it (Step 4D); empty while it's voided. */
    state?: "issued" | "paid" | "voided" | null;
    grossCentavos?: number | null; discountCentavos?: number | null; taxCentavos?: number | null; totalCentavos?: number | null;
    lines?: InvoiceLine[] | null;
    voidReason?: string | null;
  } | null;
  /** VAT: the invoice's once invoiced, else not known yet (null). */
  taxCentavos?: number | null;
  /** The order's own amounts, as ordered (the invoice's take their place in grossCentavos… once invoiced). */
  ordered?: { grossCentavos: number; discountCentavos: number; totalCentavos: number };
  payer: { kind: string; issuer?: string; letterNumber?: string; amountCentavos?: number } | null;
  notes: string | null;
  grossCentavos: number;
  discountCentavos: number;
  decidedBy: { id: string; name: string } | null;
  decidedAt: string | null;
  decisionNote: string | null;
  deliveredAt: string | null;
  lines: { id: string; product: { id: string; sku: string; name: string; unit: string }; quantity: number; freeQuantity: number; unitPrice: number; discount: number; total: number; delivered: number;
    /** The unit sold (step 4A): a pack, or the base unit (per 1); quantity stays in the base unit. */
    unit?: { packagingId: string | null; name: string; per: number; soldAs: string | null } }[];
  deliveries: { id: string; number: string; status: string; issuedAt: string | null; shipping?: import("@/src/modules/inventory/lib/types").Shipping | null }[];
};

/** A line of the order's invoice, as Finance issued it (Step 4D). */
export type InvoiceLine = {
  ref: string | null; description: string; quantity: number; unitPriceCentavos: number; discountCentavos: number; taxCentavos: number; totalCentavos: number;
};
