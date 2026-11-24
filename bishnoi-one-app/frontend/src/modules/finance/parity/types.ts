export type CreditNoteAllocation = {
  id: string;
  invoiceId: string;
  appliedOn: string;
  amountCentavos: number;
  removedAt: string | null;
  removedBy: string | null;
};

export type CreditNoteItem = {
  id: string;
  status: "draft" | "issued" | "void";
  number: string | null;
  invoiceId: string | null;
  customer: { id: string | null; name: string; tin: string | null; address: string | null };
  treatment: string;
  date: string;
  reference: string | null;
  reason: string | null;
  totalCentavos: number;
  taxCentavos: number;
  appliedCentavos: number;
  remainingCentavos: number;
  entryId: string | null;
  createdBy: string;
  allocations: CreditNoteAllocation[];
};

export type VendorCreditAllocation = {
  id: string;
  billId: string;
  appliedOn: string;
  amountCentavos: number;
  removedAt: string | null;
  removedBy: string | null;
};

export type VendorCreditItem = {
  id: string;
  status: "draft" | "recorded" | "void";
  number: string | null;
  billId: string | null;
  supplier: { id: string; name: string; tin: string | null };
  date: string;
  reference: string;
  reason: string | null;
  netCentavos: number;
  vatCentavos: number;
  withheldCentavos: number;
  totalCentavos: number;
  creditCentavos: number;
  appliedCentavos: number;
  remainingCentavos: number;
  entryId: string | null;
  createdBy: string;
  allocations: VendorCreditAllocation[];
};

export type AdvanceApplication = {
  id: string;
  targetKind: "bill" | "invoice";
  targetId: string;
  appliedOn: string;
  amountCentavos: number;
  entryId: string | null;
  removedAt: string | null;
  removedBy: string | null;
};

export type AdvanceItem = {
  id: string;
  kind: "supplier" | "customer";
  status: "posted" | "void";
  number: string;
  partyId: string | null;
  partyName: string;
  date: string;
  method: string;
  bankAccountId: string | null;
  advanceAccountId: string;
  reference: string | null;
  notes: string | null;
  amountCentavos: number;
  appliedCentavos: number;
  remainingCentavos: number;
  applications: AdvanceApplication[];
};

export type RecurringItem = {
  id: string;
  kind: "bill" | "invoice";
  name: string;
  frequency: "weekly" | "monthly" | "quarterly" | "yearly";
  startDate: string;
  endDate: string | null;
  nextRunDate: string;
  isActive: boolean;
  isDue: boolean;
  payload: Record<string, unknown>;
  generatedCount: number;
  lastRunAt: string | null;
  createdBy: string;
};

export type DocumentScanItem = {
  id: string;
  fileName: string;
  contentType: string;
  size: number;
  status: "ready" | "linked";
  rawText: string | null;
  parsed: {
    supplierId: string | null;
    supplierName: string | null;
    tin: string | null;
    billDate: string | null;
    billNumber: string | null;
    totalCentavos: number | null;
    vatCentavos: number | null;
    netCentavos: number | null;
    vat: "vat" | "zero" | "exempt" | "none";
    confidence: "high" | "medium" | "low" | "manual";
    warnings: string[];
  } | null;
  linkedBillId: string | null;
  createdBy: string;
  createdAt: string;
};
