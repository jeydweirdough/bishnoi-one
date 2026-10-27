export type Balance = { owedCentavos: number; reservedCentavos: number; availableCentavos: number };
export type Aging = {
  on: string;
  billCount: number;
  totals: Balance;
  buckets: { key: string; label: string; amountCentavos: number }[];
  suppliers: (Balance & {
    id: string; name: string; oldestDaysLate: number; buckets: Record<string, number>;
    bills: (Balance & { id: string; no: number; invoice: string; dueDate: string; bucket: string; daysLate: number })[];
  })[];
};
export type PayablesWork = {
  on: string; aging: Aging | null;
  queues: { key: string; label: string; group: string; unit: string; count: number; href: string;
    amountCentavos: number; reservedCentavos: number; availableCentavos: number;
    details: { id: string; label: string; href: string; note: string | null }[] }[];
};
