import { Sheet } from "@/src/platform/ui/sheet";
import { plural } from "@/src/platform/lib/format";
import { rateLabel } from "@/src/platform/lib/labels";
import type { RetentionRules, RetentionSummary } from "@/src/platform/lib/types";

function Tile({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <div className="min-w-0 px-5 py-4">
      <span className="block text-figure text-ink [font-variant-numeric:proportional-nums]">{value}</span>
      <span className="mt-0.5 block text-meta text-ink-3">{label}</span>
      {note && <span className="block text-meta text-ink-3">{note}</span>}
    </div>
  );
}

/** The one number the page leads with, then the counts behind it. */
export function RetentionFigures({ summary, rules }: { summary: RetentionSummary; rules: RetentionRules }) {
  return (
    <Sheet className="mb-5 grid lg:grid-cols-[18rem_minmax(0,1fr)]">
      <div className="border-b border-rule px-5 py-5 lg:border-r lg:border-b-0">
        <p className="text-meta font-medium text-ink-2">Retention, last {rules.lostDays} days</p>
        <p className="mt-1 text-5xl leading-none font-semibold tracking-tight text-ink [font-variant-numeric:proportional-nums]">
          {rateLabel(summary.rate)}
        </p>
        <p className="mt-2 text-meta text-ink-3">
          {summary.base
            ? `${summary.retained} of the ${plural(summary.base, "customer")} who got a quote in the ${rules.lostDays} days before got another since.`
            : `Nobody got a quote in the ${rules.lostDays} days before, so there's nothing to compare yet.`}
        </p>
      </div>
      {/* A 1px gap over the rule colour draws the hairlines between tiles at every width. */}
      <div className="grid grid-cols-2 gap-px bg-rule sm:grid-cols-3 [&>*]:bg-sheet">
        <Tile label="Kept" value={summary.retained} />
        <Tile label="Lost" value={summary.lost} note="no quote since" />
        <Tile label="New customers" value={summary.new} note="first quote" />
        <Tile label="At risk now" value={summary.atRisk} note={`no quote in ${rules.atRiskDays}+ days`} />
        <Tile label="Healthy now" value={summary.healthy} />
        <Tile label="No recent quotes" value={summary.noQuotes} />
      </div>
    </Sheet>
  );
}
