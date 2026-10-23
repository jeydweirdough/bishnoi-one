import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { Ring, Tile } from "@/src/platform/ui/figures";
import { plural } from "@/src/platform/lib/format";
import { rateLabel } from "@/src/platform/lib/labels";
import type { RetentionRules, RetentionSummary } from "@/src/platform/lib/types";

/**
 * Where the page starts: the rate, in its own block (or, with nothing to
 * measure yet, what it's waiting for); then the counts behind it, a tile each,
 * those to act on first.
 */
export function RetentionFigures({ summary, rules }: { summary: RetentionSummary; rules: RetentionRules }) {
  const measured = summary.rate !== null;
  const pct = measured ? Math.round(summary.rate! * 100) : null;
  return (
    <div className="mb-5 grid gap-3 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <Sheet className="px-5 py-4">
        <p className="text-caps text-ink-3 uppercase">Retention, last {rules.lostDays} days</p>
        {measured ? (
          <div className="mt-3 flex items-start justify-between gap-3 rounded-xl bg-mint px-4 py-4">
            <div className="min-w-0">
              <p className="text-[2.25rem] leading-tight font-semibold tracking-[-0.02em] text-ink tabular-nums">{rateLabel(summary.rate)}</p>
              <p className="mt-1 text-sm font-medium text-ink">of customers kept</p>
              <p className="mt-1 text-meta text-ink-3">
                {summary.retained} of the {plural(summary.base, "customer")} quoted in the {rules.lostDays} days before got another quote since.
              </p>
            </div>
            <Ring pct={pct ?? 0} size="lg" />
          </div>
        ) : (
          // Nothing to measure yet: the same drawing and words as every empty place.
          <div className="mt-3 rounded-xl bg-mint">
            <Empty compact icon="trend" title="Not enough data to compare">
              It shows once customers quoted in one {rules.lostDays}-day window can be compared with the next. Keep quoting, and it fills in.
            </Empty>
          </div>
        )}
      </Sheet>
      <div className="grid auto-rows-fr grid-cols-2 gap-3 sm:grid-cols-3">
        <Tile figure={{ value: String(summary.atRisk), label: "At risk now", note: `no quote in ${rules.atRiskDays}+ days`, href: "#worth-a-call", alert: summary.atRisk > 0 }} />
        <Tile figure={{ value: String(summary.lost), label: "Lost", note: "no quote since", href: "#worth-a-call" }} />
        <Tile figure={{ value: String(summary.noQuotes), label: "No recent quotes", note: "never quoted lately" }} />
        <Tile figure={{ value: String(summary.retained), label: "Kept", note: "quoted again" }} />
        <Tile figure={{ value: String(summary.new), label: "New customers", note: "first quote" }} />
        <Tile figure={{ value: String(summary.healthy), label: "Active customers", note: `quoted in ${rules.atRiskDays} days` }} />
      </div>
    </div>
  );
}
