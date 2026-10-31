/** The Admin Console Home's periods: what the cards count, compared with the period just before. */
export const PERIODS = [
  { value: "week", label: "Last 7 days", since: "vs the 7 days before" },
  { value: "month", label: "Last 30 days", since: "vs the 30 days before" },
  { value: "quarter", label: "Last 90 days", since: "vs the 90 days before" },
  { value: "year", label: "Last 12 months", since: "vs the year before" },
] as const;

export type PeriodKey = (typeof PERIODS)[number]["value"];

/** The period asked for in the address, or the 30 days by default. */
export const periodOf = (asked: unknown): PeriodKey => PERIODS.find((p) => p.value === asked)?.value ?? "month";
