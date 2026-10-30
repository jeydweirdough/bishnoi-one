// Petty cash, as Finance's API answers it (app/routers/petty_cash.py). One voucher (PCV) per
// paper voucher, with a line for each receipt; money in centavos, rates in basis points.

export type PettyCashStatus = "draft" | "to_check" | "returned" | "posted" | "void";
export type PettyCashShow = PettyCashStatus | "all";

export type PettyCashFund = { id: string; code: string; name: string; active: boolean; balanceCentavos: number };

export type PettyCashMay = { canEdit: boolean; canSubmit: boolean; canCheck: boolean; canReturn: boolean; canVoid: boolean; canDelete: boolean };

export type PettyCashSummary = {
  id: string;
  number: string;
  status: PettyCashStatus;
  statusLabel: string;
  voucherDate: string;
  fund: { id: string; code: string; name: string };
  personInCharge: string | null;
  department: string | null;
  receipts: number;
  missingReceipts: number;
  totalCentavos: number;
  paidOutCentavos: number;
  createdBy: string;
} & PettyCashMay;

export type ReceiptFile = { name: string; contentType: string; size: number; uploadedBy: string; uploadedAt: string | null };

export type PettyCashLine = {
  id: string;
  position: number;
  spentOn: string;
  store: string;
  storeTin: string | null;
  receiptNumber: string;
  account: { id: string; code: string; name: string };
  description: string | null;
  purchaseType: string;
  purchaseTypeLabel: string;
  vat: string;
  vatLabel: string;
  withholding: string | null;
  withholdingRateBp: number | null;
  amountCentavos: number;
  netCentavos: number;
  vatCentavos: number;
  withheldCentavos: number;
  file: ReceiptFile | null;
};

export type PettyCashEvent = { at: string; kind: string; who: string; text: string | null };

export type PettyCashVoucher = PettyCashSummary & {
  amountsIncludeVat: boolean;
  notes: string | null;
  lines: PettyCashLine[];
  netCentavos: number;
  vatCentavos: number;
  withheldCentavos: number;
  entryId: string | null;
  createdAt: string;
  submittedAt: string | null;
  checkedBy: string | null;
  checkedAt: string | null;
  voidedBy: string | null;
  voidedAt: string | null;
  voidReason: string | null;
  events: PettyCashEvent[];
};

export type PettyCashList = {
  items: PettyCashSummary[];
  limited: boolean;
  counts: Record<PettyCashShow, number>;
  waitingForYou: number;
  waitingOnOthers: number;
  funds: PettyCashFund[];
  may: { create: boolean; check: boolean; void: boolean };
};

export type PettyCashChoices = {
  funds: PettyCashFund[];
  accounts: { id: string; code: string; name: string; type: "expense" | "asset" | string }[];
  vatKinds: { key: string; label: string }[];
  purchaseTypes: { key: string; label: string }[];
  withholding: { code: string; name: string; rateBp: number }[];
  people: string[];
  departments: string[];
};

export type PettyCashLineInput = {
  id?: string;
  spentOn: string;
  store: string;
  storeTin: string | null;
  receiptNumber: string;
  accountId: string;
  description: string | null;
  purchaseType: string;
  vat: string;
  withholding: string | null;
  amountCentavos: number;
};

export type PettyCashInput = {
  number: string;
  fundAccountId: string;
  voucherDate: string;
  personInCharge: string | null;
  department: string | null;
  notes: string | null;
  amountsIncludeVat: boolean;
  lines: PettyCashLineInput[];
};

/** Where a receipt opens in the browser (the file route in app/(app)/finance/petty-cash/[id]/files/[line]). */
export const receiptUrl = (voucherId: string, lineId: string) => `/finance/petty-cash/${voucherId}/files/${lineId}`;

/** A receipt the browser can draw inline. HEIC is kept as sent and opens in its own tab. */
export const showsInline = (contentType: string) => /^image\/(jpeg|png|webp)$/.test(contentType);
