// The ledger, as Finance's API answers it (app/routers/ledger.py).

export type AccountType = "asset" | "liability" | "equity" | "income" | "expense";

export type Account = { id: string; code: string; name: string; type: AccountType; description: string | null; isActive: boolean };

export type Chart = { items: Account[]; types: { key: AccountType; label: string }[]; canEdit: boolean };

export type EntryLine = {
  account: { id: string; code: string; name: string };
  debitCentavos: number;
  creditCentavos: number;
  description: string | null;
};

export type Entry = {
  id: string;
  number: string;
  date: string;
  memo: string;
  reference: string | null;
  /** manual: a journal Finance wrote. fund: posted by a marketing request's step. */
  source: "manual" | "fund";
  fundRequestId: string | null;
  reversesId: string | null;
  reversedById: string | null;
  postedBy: string;
  lines: EntryLine[];
  totalCentavos: number;
};

export type AccountLedger = {
  account: Account;
  openingCentavos: number;
  closingCentavos: number;
  lines: { entryId: string; number: string; date: string; memo: string; description: string | null; debitCentavos: number; creditCentavos: number; balanceCentavos: number }[];
};

export type TrialBalance = {
  to: string;
  rows: { account: Account; debitCentavos: number; creditCentavos: number; balanceCentavos: number }[];
  debitCentavos: number;
  creditCentavos: number;
};

export type Posting = { items: { key: string; label: string; type: AccountType; account: Account | null }[]; canEdit: boolean };

export const TYPE_LABELS: Record<AccountType, string> = { asset: "Assets", liability: "Liabilities", equity: "Equity", income: "Income", expense: "Expenses" };
