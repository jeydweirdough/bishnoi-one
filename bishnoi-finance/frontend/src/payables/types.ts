// Payables, as Finance's API answers them (app/routers/payables.py). Money in centavos;
// rates in basis points (100 = 1%).

export type Withholding = { code: string; name: string; rateBp: number };

/** Someone else at the supplier (Zoho's Contact Persons). */
export type SupplierContact = {
  salutation: string | null;
  firstName: string | null;
  lastName: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  designation: string | null;
};

export type Supplier = {
  id: string;
  no: number | null;
  /** How they're shown (Zoho's Display Name). */
  name: string;
  /** As registered. */
  companyName: string | null;
  /** The primary contact. */
  salutation: string | null;
  firstName: string | null;
  lastName: string | null;
  mobile: string | null;
  /** Their bills post here instead of the default (e.g. AP - Trade). */
  payablesAccount: { id: string; code: string; name: string } | null;
  contacts: SupplierContact[];
  /** Their papers: BIR 2303, accreditation. */
  files: BillFile[];
  /** Their recorded bills, not yet paid. */
  owedCentavos: number;
  tin: string | null;
  branchCode: string | null;
  address: string | null;
  vatRegistered: boolean;
  withholding: Withholding | null;
  termsDays: number;
  email: string | null;
  phone: string | null;
  bankName: string | null;
  bankAccountName: string | null;
  bankAccountNumber: string | null;
  notes: string | null;
  isActive: boolean;
  createdBy: string;
};

/** A supplier from an import, as it would be saved (app/routers/payables.py, /suppliers/import/check). */
export type ImportedSupplier = {
  name: string;
  companyName: string | null;
  salutation: string | null;
  firstName: string | null;
  lastName: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  tin: string | null;
  branchCode: string | null;
  address: string | null;
  termsDays: number;
  notes: string | null;
  isActive: boolean;
};

export type SupplierImportRow = { line: number; status: "new" | "here" | "problem"; note: string | null; supplier: ImportedSupplier };

export type SupplierImportCheck = { rows: SupplierImportRow[]; counts: { new: number; here: number; problem: number } };

export type BillStatus = "draft" | "recorded" | "void";

export const BILL_STATUS_LABELS: Record<BillStatus, string> = { draft: "Draft", recorded: "Recorded", void: "Void" };

export type BillSummary = {
  id: string;
  no: number | null;
  status: BillStatus;
  statusLabel: string;
  supplier: { id: string; name: string };
  billNumber: string;
  billDate: string;
  dueDate: string;
  totalCentavos: number;
  payableCentavos: number;
  /** No photo or PDF of the supplier's invoice attached yet (Aubrey Q20). */
  documentMissing: boolean;
  createdBy: string;
};

export type VatKind = "vat" | "zero" | "exempt" | "none";

/** A line as the form sends it. */
export type BillLineInput = { accountId: string; description: string | null; amountCentavos: number; vat: VatKind; withholding: string | null };

export type BillLine = BillLineInput & {
  account: { id: string; code: string; name: string } | null;
  vatLabel: string;
  withholdingRateBp: number | null;
  netCentavos?: number;
  vatCentavos?: number;
  withheldCentavos?: number;
};

export type BillFile = { id: string; name: string; contentType: string; size: number; uploadedBy: string; uploadedAt: string };

export type Bill = Omit<BillSummary, "supplier"> & {
  supplier: Supplier;
  poNumber: string | null;
  drNumber: string | null;
  checkedPo: boolean;
  checkedDr: boolean;
  amountsIncludeVat: boolean;
  zohoRef: string | null;
  oojeemaRef: string | null;
  notes: string | null;
  lines: BillLine[];
  netCentavos: number;
  vatCentavos: number;
  withheldCentavos: number;
  /** Why a draft's amounts can't be worked out (e.g. no VAT rate for its date). */
  problem: string | null;
  files: BillFile[];
  entryId: string | null;
  recordedBy: string | null;
  recordedAt: string | null;
  voidedBy: string | null;
  voidedAt: string | null;
  voidReason: string | null;
};

export type BillChoices = {
  suppliers: Supplier[];
  accounts: { id: string; code: string; name: string; type: "expense" | "asset" }[];
  vatKinds: { key: VatKind; label: string }[];
  withholding: Withholding[];
  today: string;
};
