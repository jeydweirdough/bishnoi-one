// The Overview's dashboard, as GET /finance/dashboard sends it: only the
// sections this person's role calls for (app/routers/finance.py).

export type Bucket = { key: string; label: string; amountCentavos: number };
export type Invoiced = { count: number; totalCentavos: number; taxCentavos: number };

export type Section =
  | {
      key: "waiting";
      canApproveEntries: boolean;
      entriesToApprove: number;
      canApprovePrices: boolean;
      canRelease: boolean;
      toRelease: number;
      canReview: boolean;
      toReview: number;
      canSettle: boolean;
      toSettle: number;
      overdueLiquidations: number;
    }
  | { key: "receivables"; totalCentavos: number; buckets: Bucket[]; customers: number; mostOverdue: { name: string; owedCentavos: number; oldestDaysLate: number }[] }
  | { key: "sales"; month: Invoiced; year: Invoiced }
  | { key: "spending"; teams: { team: string; yearCentavos: number; monthCentavos: number }[] }
  | {
      key: "journal";
      latest: { id: string; number: string; date: string; memo: string; postedBy: string; source: string; status: string; totalCentavos: number }[];
      thisMonth: number;
      /** This person's own entries still waiting for someone else's approval. */
      myWaiting: number;
      balanced: boolean;
    }
  | { key: "tax"; notSetUp: Record<string, number>; quarter: string; quarterInvoices: number; quarterTaxCentavos: number }
  | { key: "cash" };

export type Dashboard = { kept: true; sections: [] } | { kept: false; on: string; sections: Section[] };

export type WaitingPrices = { available: true; prices: number; quotes: number } | { available: false; message: string };
