// The ledger, as Finance's API answers it (app/routers/ledger.py).

export type AccountType = "asset" | "liability" | "equity" | "income" | "expense";

export type Account = {
  id: string;
  code: string;
  name: string;
  type: AccountType;
  description: string | null;
  isActive: boolean;
  /** The account it sits under (Oojeema's chart groups them); none: at the top. */
  parentId: string | null;
  /** Assets and liabilities: current (within a year) or long-term; null: worked out from the name. */
  term: "current" | "non_current" | null;
  /** What the management figures count it as (term, or worked out from the name); null for other types. */
  termShown: "current" | "non_current" | null;
};

/** One row of a chart being imported, as the API would save it (app/routers/ledger.py). */
export type ImportRow = {
  line: number;
  code: string;
  name: string;
  kind: string | null;
  type: AccountType | null;
  parent: string | null;
  /** Where the parent was found: in the file, already in the chart, or nowhere. */
  parentFound: "file" | "chart" | null;
  description: string | null;
  status: "new" | "here" | "problem";
  note: string | null;
  /** What's wrong: "code", "name", "type". Only a missing type can be put right here. */
  problems: ("code" | "name" | "type")[];
};

export type ImportCheck = { rows: ImportRow[]; counts: { new: number; here: number; problem: number }; types: { key: AccountType; label: string }[] };

export type ImportAccount = { code: string; name: string; type: AccountType; description: string | null; parent: string | null };

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
  /** Typed by hand, an entry waits until someone else approves it; only approved ones count (2026-10-22). */
  status: EntryStatus;
  decidedBy: string | null;
  decidedAt: string | null;
  rejectedReason: string | null;
  /** Whether the person looking may approve or reject it now (not their own, and still waiting). */
  canDecide: boolean;
  /** Where the entry that reverses this one stands: until it's approved, this one still counts. */
  reversalStatus: EntryStatus | null;
  lines: EntryLine[];
  totalCentavos: number;
};

export type EntryStatus = "approved" | "waiting" | "rejected";

/** Ties each entry's tick box on the journal page to the "Approve selected" bar (decide.tsx). */
export const BULK_FORM = "approve-several";

export type AccountLedger = {
  account: Account;
  openingCentavos: number;
  closingCentavos: number;
  lines: { entryId: string; number: string; date: string; memo: string; description: string | null; debitCentavos: number; creditCentavos: number; balanceCentavos: number }[];
};

export type TrialBalance = {
  to: string;
  /** Entries up to that day still waiting for approval: not in these figures yet. */
  waiting: number;
  rows: { account: Account; debitCentavos: number; creditCentavos: number; balanceCentavos: number }[];
  debitCentavos: number;
  creditCentavos: number;
};

export type Posting = { items: { key: string; label: string; type: AccountType; account: Account | null }[]; canEdit: boolean };

export const TYPE_LABELS: Record<AccountType, string> = { asset: "Assets", liability: "Liabilities", equity: "Equity", income: "Income", expense: "Expenses" };
