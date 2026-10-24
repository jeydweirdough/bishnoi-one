// Bank reconciliation (decided 2026-10-24, from Oojeema): what Finance's API answers (/finance/bank).

export type BankAccount = { id: string; code: string; name: string; bookBalanceCentavos: number; lastReconciled: string | null; lastStatementBalanceCentavos: number | null; openId: string | null };

export type ReconciliationSummary = {
  id: string; account: { id: string; code: string; name: string }; status: "open" | "done";
  statementDate: string; statementBalanceCentavos: number; createdBy: string; finishedBy: string | null; finishedAt: string | null;
};

export type Reconciliation = ReconciliationSummary & {
  openingBalanceCentavos: number; bookBalanceCentavos: number;
  lines: { id: number; date: string; number: string; memo: string; reference: string | null; inCentavos: number; outCentavos: number; cleared: boolean }[];
  clearedInCentavos: number; clearedOutCentavos: number; clearedBalanceCentavos: number; differenceCentavos: number;
};
