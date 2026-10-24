// Supplier bills (decided 2026-10-24, BIR features from Oojeema): what Finance's API answers (/finance/bills).

export type BillSupplier = { id: string; code?: string; name: string; tin: string | null; address: string | null; vatStatus: string; defaultAtc?: string | null; paymentTerms?: string | null };

export type BillLine = { description: string; accountId: string; kind: string; amountCentavos: number; withheld: boolean };

export type ComputedLine = BillLine & { netCentavos: number; vatCentavos: number; account: { code: string; name: string } | null };

export type Bill = {
  id: string; no: number | null; status: "draft" | "posted" | "void";
  supplier: BillSupplier;
  supplierInvoiceNo: string; billDate: string; termsDays: number; dueDate: string;
  deliveryRef: string | null; notes: string | null; amountsIncludeVat: boolean;
  atc: string | null; ewtRateBp: number;
  totalCentavos: number; inputTaxCentavos: number; ewtCentavos: number; payableCentavos: number; paidCentavos: number; balanceCentavos: number;
  createdBy: string; postedBy: string | null; voidedBy: string | null; voidReason: string | null;
  computed?: { lines: ComputedLine[]; netCentavos: number; byKind: Record<string, number>; vatRateBp: number; atcNature: string | null; ewtBaseCentavos: number };
  payments?: { id: string; paidOn: string; amountCentavos: number; method: string; methodLabel: string; reference: string | null; recordedBy: string; removedBy: string | null; removedAt: string | null }[];
  methods?: { key: string; label: string }[];
};

export type BillSetup = {
  kinds: { key: string; label: string }[];
  atcs: { code: string; nature: string; rateBp: number }[];
  accounts: { id: string; code: string; name: string; type: string }[];
  methods: { key: string; label: string }[];
};

export type Delivery = { id: string; number: string; receivedAt: string; deliveryRef: string | null; order: string | null; lines: { product: string; sku: string; quantity: number; unitCost: number; amount: number }[]; totalCost: number };

export type Payables = {
  asOf: string;
  buckets: { key: string; label: string }[];
  items: ({ supplier: { id: string; name: string }; owedCentavos: number } & Record<string, unknown>)[];
  totals: Record<string, number>;
};
