// Payment vouchers, as Finance's API answers them (app/routers/vouchers.py). Money in centavos.

import type { BillFile } from "../payables/types";

// to_check and to_approve were the voucher's own checks until they moved to the bill (2026-10-23).
export type VoucherStatus = "draft" | "returned" | "to_check" | "to_approve" | "to_release" | "released" | "cancelled" | "void";
export type VoucherMethod = "bank" | "check" | "cash";

export const VOUCHER_STATUS_LABELS: Record<VoucherStatus, string> = {
  draft: "Draft",
  returned: "Returned",
  to_check: "To check",
  to_approve: "To approve",
  to_release: "To release",
  released: "Released",
  cancelled: "Cancelled",
  void: "Void",
};

export type AccountBrief = { id: string; code: string; name: string };

export type VoucherSummary = {
  id: string;
  no: number | null;
  number: string;
  status: VoucherStatus;
  statusLabel: string;
  supplier: { id: string; name: string };
  method: VoucherMethod;
  methodLabel: string;
  totalCentavos: number;
  bills: number;
  preparedBy: string;
  oojeemaRef: string | null;
  paidOn: string | null;
  updatedAt: string | null;
};

/** One bill a voucher pays: its total, paid before this voucher, paying now, left after (shown plainly: decision 4). */
export type VoucherLine = {
  billId: string;
  billNo: number | null;
  billNumber: string;
  billDate: string;
  dueDate: string;
  payableCentavos: number;
  paidBeforeCentavos: number;
  setAsideElsewhereCentavos: number;
  amountCentavos: number;
  leftAfterCentavos: number;
  partial: boolean;
  documentMissing: boolean;
  files: BillFile[];
  /** The bill's own approvals (Aubrey's flow): who approved it, and who checked its tax withheld. */
  approvedBy: string | null;
  checkedBy: string | null;
  withheldCentavos: number;
};

export type VoucherEvent = { at: string; kind: string; who: string; text: string | null };

export type Voucher = Omit<VoucherSummary, "supplier"> & {
  supplier: {
    id: string;
    name: string;
    companyName: string | null;
    tin: string | null;
    branchCode: string | null;
    address: string | null;
    bankName: string | null;
    bankAccountName: string | null;
    bankAccountNumber: string | null;
  };
  paidFrom: AccountBrief | null;
  lines: VoucherLine[];
  amountInWords: string;
  zohoRef: string | null;
  notes: string | null;
  releasedBy: string | null;
  bankReference: string | null;
  checkNumber: string | null;
  checkDate: string | null;
  entryId: string | null;
  events: VoucherEvent[];
  files: BillFile[];
  canEdit: boolean;
  canSubmit: boolean;
  canRelease: boolean;
  canReturn: boolean;
  canCancel: boolean;
  canVoid: boolean;
  canAttach: boolean;
};

/** A supplier's bill a voucher can pay: what's paid, what other open vouchers set aside, what's left. */
export type PayableBill = {
  id: string;
  no: number | null;
  billNumber: string;
  billDate: string;
  dueDate: string;
  payableCentavos: number;
  paidCentavos: number;
  setAsideCentavos: number;
  availableCentavos: number;
  documentMissing: boolean;
};

export type VoucherChoices = {
  suppliers: { id: string; name: string; owedCentavos: number }[];
  supplier: { id: string; name: string; bankName: string | null; bankAccountName: string | null; bankAccountNumber: string | null } | null;
  bills: PayableBill[];
  accounts: AccountBrief[];
  methods: { key: VoucherMethod; label: string }[];
  today: string;
};
