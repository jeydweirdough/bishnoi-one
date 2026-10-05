// Sales invoices, as the API sends them (app/routers/invoices.py).

export type InvoiceStatus = "draft" | "issued" | "void";

export type InvoiceLine = {
  ref: string | null;
  description: string | null;
  quantity: number;
  unitPriceCentavos: number;
  discountCentavos: number;
  category: string;
  reliefEligible: boolean;
};

/** The tax engine's answer: the invoice as it prints (app/routers/tax.py work_out). */
export type Computed = {
  document: string;
  on: string;
  pricesIncludeTax: boolean;
  seller: { registeredName: string | null; tradeName: string | null; tin: string | null; address: string | null; regime: string; regimeName: string };
  buyer: { name: string | null; tin: string | null; address: string | null; idNumber: string | null };
  treatment: { key: string; name: string };
  lines: {
    ref: string | null;
    description: string | null;
    code: string;
    codeName: string;
    priceCentavos: number;
    reliefCentavos: number;
    taxCentavos: number;
    totalCentavos: number;
  }[];
  summary: { key: string; label: string; amountCentavos: number }[];
  relief: { label: string; amountCentavos: number } | null;
  totalDueCentavos: number;
  notice: string | null;
  warnings: string[];
};

export type InvoiceSummary = {
  id: string;
  status: InvoiceStatus;
  number: string | null;
  customer: { id: string | null; name: string; tin: string | null; address: string | null };
  treatment: string;
  buyerIdNumber: string | null;
  date: string;
  termsDays: number;
  dueDate: string;
  reference: string | null;
  notes: string | null;
  pricesIncludeTax: boolean | null;
  totalCentavos: number;
  taxCentavos: number;
  paidCentavos: number;
  balanceCentavos: number;
  createdBy: string;
  issuedBy: string | null;
  issuedAt: string | null;
  voidedBy: string | null;
  voidedAt: string | null;
  voidReason: string | null;
  series: { id: string; name: string; atpNumber: string; atpDate: string; range: string } | null;
};

export type Payment = {
  id: string;
  paidOn: string;
  amountCentavos: number;
  method: string;
  methodLabel: string;
  reference: string | null;
  recordedBy: string;
  recordedAt: string;
  removedBy: string | null;
  removedAt: string | null;
};

export type Invoice = InvoiceSummary & {
  lines: InvoiceLine[];
  entryId: string | null;
  computed: Computed | null;
  problem: string | null;
  payments: Payment[];
  methods: { key: string; label: string }[];
};

/** What customers owe, by how late (app/routers/receivables.py). */
export type Ageing = {
  on: string;
  buckets: { key: string; label: string; amountCentavos: number }[];
  totalCentavos: number;
  customers: {
    customerId: string | null;
    name: string;
    totalCentavos: number;
    buckets: Record<string, number>;
    oldestDaysLate: number;
    invoices: { id: string; number: string; date: string; dueDate: string; daysLate: number; bucket: string; totalCentavos: number; owedCentavos: number }[];
  }[];
};

export type Series = {
  id: string;
  name: string;
  prefix: string;
  digits: number;
  firstNumber: string;
  lastNumber: string;
  nextNumber: string | null;
  left: number;
  atpNumber: string;
  atpDate: string;
  isActive: boolean;
};

export type Customer = { id: string; name: string; status: string; address: string | null; email: string | null; phone: string | null; tin: string | null };

/** What the invoice form picks from: the tax pack's VAT categories and kinds of buyer. */
export type TaxChoices = {
  categories: { key: string; name: string }[];
  treatments: { key: string; name: string; needsId: boolean }[];
  pricesIncludeTax: boolean;
};

export const STATUS_LABELS: Record<InvoiceStatus, string> = { draft: "Draft", issued: "Issued", void: "Void" };
