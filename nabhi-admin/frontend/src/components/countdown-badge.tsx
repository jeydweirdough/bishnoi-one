import type { UrgencyTier } from "@/src/platform/lib/types";
import { Flag } from "@/src/platform/ui/marks";

export function CountdownBadge({
  daysRemaining,
  urgencyTier,
  compact = false,
}: {
  daysRemaining: number | null | undefined;
  urgencyTier?: UrgencyTier;
  compact?: boolean;
}) {
  if (daysRemaining === null || daysRemaining === undefined) {
    return <span className="text-meta text-ink-3">No date set</span>;
  }

  if (daysRemaining < 0) {
    const overdueDays = Math.abs(daysRemaining);
    return (
      <Flag letter="!">
        <span className="font-semibold text-danger">
          OVERDUE · {overdueDays}d {compact ? "" : "ago"}
        </span>
      </Flag>
    );
  }

  if (daysRemaining <= 15) {
    return (
      <span className="inline-flex items-center gap-1 rounded-[2px] bg-eosin-tint px-1.5 py-0.5 text-stamp font-semibold text-eosin uppercase">
        <span className="size-1.5 rounded-full bg-eosin" />
        {daysRemaining === 0 ? "Due Today" : `${daysRemaining}d left`}
      </span>
    );
  }

  if (daysRemaining <= 30) {
    return (
      <span className="inline-flex items-center gap-1 rounded-[2px] bg-hema-tint px-1.5 py-0.5 text-stamp font-semibold text-hema uppercase">
        <span className="size-1.5 rounded-full bg-hema" />
        {daysRemaining}d left
      </span>
    );
  }

  if (daysRemaining <= 60) {
    return (
      <span className="inline-flex items-center rounded-[2px] border border-rule-strong px-1.5 py-0.5 text-stamp font-medium text-ink-2 uppercase">
        {daysRemaining}d left
      </span>
    );
  }

  return (
    <span className="inline-flex items-center rounded-[2px] px-1 text-stamp text-ink-3 uppercase">
      {daysRemaining}d left
    </span>
  );
}

export function UrgencyMark({ tier }: { tier: UrgencyTier }) {
  switch (tier) {
    case "overdue":
      return (
        <span className="inline-flex items-center rounded-[2px] bg-danger-tint px-1.5 py-0.5 text-stamp font-bold text-danger uppercase">
          Overdue
        </span>
      );
    case "urgent":
      return (
        <span className="inline-flex items-center rounded-[2px] bg-eosin-tint px-1.5 py-0.5 text-stamp font-semibold text-eosin uppercase">
          Urgent (&le;15d)
        </span>
      );
    case "approaching":
      return (
        <span className="inline-flex items-center rounded-[2px] bg-hema-tint px-1.5 py-0.5 text-stamp font-semibold text-hema uppercase">
          Approaching (&le;30d)
        </span>
      );
    case "upcoming":
      return (
        <span className="inline-flex items-center rounded-[2px] border border-rule px-1.5 py-0.5 text-stamp text-ink-2 uppercase">
          Upcoming (&le;60d)
        </span>
      );
    case "good_standing":
      return (
        <span className="inline-flex items-center rounded-[2px] px-1 text-stamp text-ink-3 uppercase">
          Good Standing
        </span>
      );
    default:
      return null;
  }
}
