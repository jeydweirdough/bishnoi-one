import type { DealRow, ForecastCategory } from "@/src/platform/lib/types";

// How deals are worded on every screen.

export const CATEGORY_LABELS: Record<ForecastCategory, string> = {
  pipeline: "Pipeline",
  best_case: "Best case",
  commit: "Commit",
  closed: "Closed",
  omitted: "Omitted",
};

/** What a rep can say about an open deal: "closed" comes only with winning it. */
export const OPEN_CATEGORIES: { value: Exclude<ForecastCategory, "closed">; label: string; hint: string }[] = [
  { value: "pipeline", label: "Pipeline", hint: "Possible, not yet likely" },
  { value: "best_case", label: "Best case", hint: "Could close this period if things go well" },
  { value: "commit", label: "Commit", hint: "You're confident it closes this period" },
  { value: "omitted", label: "Omitted", hint: "Left out of the forecast" },
];

const STATE_STYLE: Record<DealRow["state"], string> = {
  open: "bg-hema-tint text-hema",
  won: "bg-filed/10 text-filed",
  lost: "bg-danger-tint text-danger",
};

/** The deal's stage, coloured by whether it's open, won or lost. */
export function StageTag({ deal }: { deal: Pick<DealRow, "state" | "stage"> }) {
  return (
    <span className={`inline-flex items-center rounded-[3px] px-2 py-0.5 text-meta font-semibold whitespace-nowrap ${STATE_STYLE[deal.state]}`}>
      {deal.stage.name}
    </span>
  );
}

/** "Due 15 Oct" for an open deal, flagged when the date has gone by. */
export function closeLabel(deal: Pick<DealRow, "state" | "expectedCloseOn" | "closedAt">, today: string, dateLabel: (key: string) => string) {
  if (deal.state !== "open") return `Closed ${dateLabel(deal.expectedCloseOn)}`;
  return deal.expectedCloseOn < today ? `Overdue: was ${dateLabel(deal.expectedCloseOn)}` : `Closes ${dateLabel(deal.expectedCloseOn)}`;
}

/** This month and next as periods (2026-10), and this quarter (2026-Q4), from a YYYY-MM-DD day. */
export function periodsFrom(today: string) {
  const y = Number(today.slice(0, 4));
  const m = Number(today.slice(5, 7));
  const month = (yy: number, mm: number) => `${yy + Math.floor((mm - 1) / 12)}-${String(((mm - 1) % 12) + 1).padStart(2, "0")}`;
  return {
    thisMonth: month(y, m),
    nextMonth: month(y, m + 1),
    thisQuarter: `${y}-Q${Math.floor((m - 1) / 3) + 1}`,
  };
}
