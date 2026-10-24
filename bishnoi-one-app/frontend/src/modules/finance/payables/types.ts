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

/** Where a bill stands (Aubrey's flow, 2026-10-23): made, approved (Malou), checked if tax is
 *  withheld (Mel), then posted and ready to pay. */
export type BillState = "draft" | "returned" | "to_approve" | "to_check" | "ready" | "partly_paid" | "paid" | "void";

export const BILL_STATE_LABELS: Record<BillState, string> = {
  draft: "Draft",
  returned: "Returned",
  to_approve: "To approve",
  to_check: "To check",
  ready: "Ready to pay",
  partly_paid: "Partly paid",
  paid: "Paid",
  void: "Void",
};

export type BillSummary = {
  id: string;
  no: number | null;
  status: BillStatus;
  statusLabel: string;
  state: BillState;
  stateLabel: string;
  supplier: { id: string; name: string };
  billNumber: string;
  billDate: string;
  dueDate: string;
  totalCentavos: number;
  payableCentavos: number;
  withheldCentavos: number;
  /** What released payment vouchers have paid; what's left; what open vouchers set aside (shown plainly: 2026-10-23). */
  paidCentavos: number;
  leftCentavos: number;
  setAsideCentavos: number;
  paymentState: "unpaid" | "partly_paid" | "paid";
  paymentLabel: string;
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
  /** Tax is withheld, so it's checked after approval (Mel). */
  needsCheck: boolean;
  /** Why a draft's amounts can't be worked out (e.g. no VAT rate for its date). */
  problem: string | null;
  files: BillFile[];
  entryId: string | null;
  /** The payment vouchers paying it (not cancelled ones). */
  vouchers: { id: string; number: string; status: string; amountCentavos: number }[];
  approvedBy: string | null;
  approvedAt: string | null;
  checkedBy: string | null;
  checkedAt: string | null;
  recordedBy: string | null;
  recordedAt: string | null;
  voidedBy: string | null;
  voidedAt: string | null;
  voidReason: string | null;
  events: { at: string; kind: string; who: string; text: string | null }[];
  /** What this person may do to it now (the API holds the same rules). */
  canEdit: boolean;
  canSubmit: boolean;
  canApprove: boolean;
  canCheck: boolean;
  canReturn: boolean;
  canVoid: boolean;
  canAttach: boolean;
  canPay: boolean;
};

export type BillChoices = {
  suppliers: Supplier[];
  accounts: { id: string; code: string; name: string; type: "expense" | "asset" }[];
  vatKinds: { key: VatKind; label: string }[];
  withholding: Withholding[];
  today: string;
};
