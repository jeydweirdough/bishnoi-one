// What GET /finance/overview sends (app/overview.py). Only what this person may see is ever in it,
// so a card or a slice that's missing here is simply not drawn.

export type PeriodKey = "month" | "quarter" | "year";
export type AreaKey = "overview" | "payables" | "receivables" | "cash" | "tax";
export type Tone = "good" | "warn" | "bad" | "plain";

export type Point = { label: string; amountCentavos: number; count: number; href: string; on?: string };
export type Bucket = { key: string; label: string; amountCentavos: number; count: number; href: string };
export type Row = {
  title: string;
  meta: string;
  href: string | null;
  amountCentavos: number | null;
  chip: { text: string; tone: Tone } | null;
  on: string | null;
  rank?: number;
  holiday?: boolean;
  records?: number;
};
export type Action = { label: string; href: string; primary: boolean; title: string | null };

export type Cards = {
  cash?: { balanceCentavos: number; changeCentavos: number; points: Point[]; href: string };
  inout?: { in: Point[]; out: Point[]; inCentavos: number; outCentavos: number };
  went?: { slices: (Bucket & { short: string; noun: string })[]; hidden: string[]; totalCentavos: number };
  ar?: { wholeCentavos: number; wholeInvoices: number; customers: number; over60Centavos: number; buckets: Bucket[]; periodCentavos: number; periodInvoices: number; href: string };
  od?: { total: number; href: string; rows: Row[] };
  coll?: { totalCentavos: number; count: number; points: Point[] };
  due?: { available: boolean; total: number; href?: string; rows: Row[] };
  zoho?: { available: boolean; buckets?: Bucket[]; companies?: Bucket[]; totalCentavos?: number; count?: number; notCounted?: number; href?: string };
  ap?: { wholeCentavos: number; wholeBills: number; over60Centavos: number; buckets: Bucket[]; periodCentavos: number; periodBills: number; dueThisWeekCentavos: number; dueThisWeek: number; href: string };
  petty?: { funds: { name: string; balanceCentavos: number; waiting: number; href: string }[]; fundCount: number; balanceCentavos: number; postedInPeriod: number; href: string };
  mkt?: { teams: { label: string; amountCentavos: number; count: number; href: string }[]; teamCount: number; totalCentavos: number; href: string };
  vat?: { vatRegistered: boolean; outputCentavos: number; inputCentavos: number; payableCentavos: number; output: Point[]; input: Point[]; href: string };
  ewt?: { totalCentavos: number; payees: number; points: Point[]; href: string };
  ready?: {
    counts: { agrees: number; differs: number; not_set: number };
    href: string;
    checks: { key: string; title: string; status: "agrees" | "differs" | "not_set"; listCentavos: number; booksCentavos: number | null; differenceCentavos: number | null; href: string }[];
  };
  books?: { sources: (Bucket & { key: string })[]; entries: number; totalCentavos: number; href: string };
  dl?: { listed: boolean };
  soon?: { rows: Row[]; total: number; href: string };
  link?: { connected: boolean; href: string; lastUpdate?: string | null; usedToday?: number; dailyLimit?: number; stoppedForToday?: boolean; error?: boolean };
  wait?: { forYou: Row[]; forYouTotal: number; byArea: Record<string, number>; seeAll: string | null; others: Row[]; othersTotal: number; prices: boolean };
};
export type CardKey = keyof Cards;

export type Stage = { key: string; label: string; count: number; noun: string; amountCentavos: number; href: string };
export type Lead = {
  key: string;
  actions: Action[];
  viewOnly?: boolean;
  rows?: Row[] | (Bucket & { noun: string })[];
  rowsTotal?: number;
  totalCentavos?: number;
  count?: number;
  oldestDays?: number;
  releasedCentavos?: number;
  releasedCount?: number;
  stages?: Stage[];
  returned?: number;
};

export type View = { lead: string; cards: CardKey[]; othersOnly: boolean };

export type OverviewData = {
  on: string;
  period: { key: PeriodKey; start: string; end: string; byUnit: string };
  cards: Cards;
  leads: Record<string, Lead>;
  views: Partial<Record<AreaKey, View>>;
  counts: Partial<Record<AreaKey, number>>;
  pickable: { key: CardKey; area: string }[];
};
