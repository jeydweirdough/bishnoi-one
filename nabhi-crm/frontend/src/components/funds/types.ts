// Marketing requests, as the API answers them (app/routers/funds.py). Once Finance
// has a request, `finance` is Finance's own copy: the release, the receipts,
// what they come to, and its record.

export type FundStatus =
  | "pending"
  | "declined"
  | "cancelled"
  | "approved"
  | "to_release"
  | "to_liquidate"
  | "to_check"
  | "to_return"
  | "to_reimburse"
  | "closed";

export type FundExpense = {
  id: string;
  spentOn: string;
  description: string;
  category: { id: string; name: string; reimbursable: boolean } | null;
  amountCentavos: number;
  receipt: { name: string } | null;
  noReceiptReason: string | null;
  /** Finance's check: null until checked. */
  accepted: boolean | null;
  refusedReason: string | null;
  /** Counts against the money released: reimbursable and not refused. */
  covered: boolean;
};

export type FinanceCopy = {
  status: string;
  release: {
    amountCentavos: number;
    method: string;
    methodLabel: string;
    reference: string | null;
    at: string;
    liquidateBy: string | null;
  } | null;
  overdue: boolean;
  sentBackNote: string | null;
  expenses: FundExpense[];
  tally: { spentCentavos: number; coveredCentavos: number; ownCentavos: number; refusedCentavos: number; balanceCentavos: number };
  returnDueCentavos: number;
  returnedCentavos: number;
  reimburseDueCentavos: number;
  reimbursedCentavos: number;
  checkedAt: string | null;
  closedAt: string | null;
  cancelReason: string | null;
  events: { at: string; kind: string; who: string; text: string; amountCentavos: number | null }[];
};

export type FundRequest = {
  id: string;
  number: string;
  purpose: { id: string | null; name: string };
  liquidate: boolean;
  amountCentavos: number;
  approvedCentavos: number | null;
  neededOn: string | null;
  details: string;
  company: { id: string; name: string } | null;
  status: FundStatus;
  statusLabel: string;
  owner: { id: string; name: string };
  team: { id: string; name: string } | null;
  decision: { by: { id: string; name: string } | null; at: string; note: string | null } | null;
  finance: FinanceCopy | null;
  financeSyncedAt: string | null;
  /** Why it couldn't be sent to Finance yet. */
  financeError: string | null;
  createdAt: string;
  can: { approve: boolean; cancel: boolean; liquidate: boolean };
};

export type FundPurpose = { id: string; name: string; description: string | null; liquidate: boolean; isActive: boolean; sortOrder: number };

/** Finance's: a category, or a sub-category (parentId) under one. */
export type ExpenseCategory = { id: string; name: string; label: string; parentId: string | null; reimbursable: boolean; description: string | null };

export type FundsWaiting = { toApprove: number; toLiquidate: number; toReturn: number };
