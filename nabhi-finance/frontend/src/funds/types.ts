// Fund requests, as Finance's API answers them (app/funds.py, request_out).

export type FundStatus = "to_release" | "to_liquidate" | "to_check" | "to_return" | "to_reimburse" | "closed" | "cancelled";

/** A category (its own account) or a sub-category (its category's account and rule). */
export type ExpenseCategory = {
  id: string;
  name: string;
  /** "Food › Dining" for a sub-category. */
  label: string;
  parentId: string | null;
  reimbursable: boolean;
  account: { id: string; code: string; name: string } | null;
  description: string | null;
  isActive: boolean;
  sortOrder: number;
};

export type FundExpense = {
  id: string;
  spentOn: string;
  description: string;
  category: { id: string; name: string; reimbursable: boolean } | null;
  amountCentavos: number;
  receipt: { name: string } | null;
  noReceiptReason: string | null;
  accepted: boolean | null;
  refusedReason: string | null;
  counts: boolean;
  covered: boolean;
};

export type FundRequest = {
  id: string;
  sourceApp: string;
  sourceId: string;
  number: string;
  requester: { name: string; email: string; team: string | null };
  purpose: string;
  details: string | null;
  customerName: string | null;
  neededOn: string | null;
  liquidate: boolean;
  requestedCentavos: number;
  approvedCentavos: number;
  approval: { by: string; at: string; note: string | null };
  status: FundStatus;
  statusLabel: string;
  release: { amountCentavos: number; method: string; methodLabel: string; reference: string | null; at: string; liquidateBy: string | null } | null;
  overdue: boolean;
  liquidatedAt: string | null;
  checkedAt: string | null;
  sentBackNote: string | null;
  expenses: FundExpense[];
  tally: { spentCentavos: number; coveredCentavos: number; ownCentavos: number; refusedCentavos: number; balanceCentavos: number };
  returnDueCentavos: number;
  returnedCentavos: number;
  reimburseDueCentavos: number;
  reimbursedCentavos: number;
  closedAt: string | null;
  cancelReason: string | null;
  events: { at: string; kind: string; who: string; text: string; amountCentavos: number | null }[];
  /** What it posted to the journal. */
  entries: { id: string; number: string; date: string; memo: string; totalCentavos: number }[];
  createdAt: string;
  updatedAt: string;
};

export type FundCounts = Record<FundStatus | "overdue", number>;

export const METHODS = [
  { value: "cash", label: "Cash" },
  { value: "bank", label: "Bank transfer" },
  { value: "ewallet", label: "E-wallet (GCash, Maya)" },
  { value: "check", label: "Check" },
] as const;
export type Method = (typeof METHODS)[number]["value"];
