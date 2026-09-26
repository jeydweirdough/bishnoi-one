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
          Overdue · {overdueDays === 1 ? "1 day" : `${overdueDays} days`}
        </span>
      </Flag>
    );
  }

  if (daysRemaining <= 15) {
    return (
      <span className="inline-flex items-center gap-1 rounded-[2px] bg-eosin-tint px-1.5 py-0.5 text-meta font-semibold text-eosin">
        <span className="size-1.5 rounded-full bg-eosin" />
        {daysRemaining === 0 ? "Due today" : daysRemaining === 1 ? "1 day left" : `${daysRemaining} days left`}
      </span>
    );
  }

  if (daysRemaining <= 30) {
    return (
      <span className="inline-flex items-center gap-1 rounded-[2px] bg-hema-tint px-1.5 py-0.5 text-meta font-semibold text-hema">
        <span className="size-1.5 rounded-full bg-hema" />
        {daysRemaining} days left
      </span>
    );
  }

  if (daysRemaining <= 60) {
    return (
      <span className="inline-flex items-center rounded-[2px] border border-rule-strong px-1.5 py-0.5 text-meta font-medium text-ink-2">
        {daysRemaining} days left
      </span>
    );
  }

  return (
    <span className="inline-flex items-center rounded-[2px] px-1 text-meta text-ink-3">
      {daysRemaining}d left
    </span>
  );
}

export function UrgencyMark({ tier }: { tier: UrgencyTier }) {
  switch (tier) {
    case "overdue":
      return (
        <span className="inline-flex items-center rounded-[2px] bg-danger-tint px-1.5 py-0.5 text-meta font-bold text-danger">
          Overdue
        </span>
      );
    case "urgent":
      return (
        <span className="inline-flex items-center rounded-[2px] bg-eosin-tint px-1.5 py-0.5 text-meta font-semibold text-eosin">
          Within 15 days
        </span>
      );
    case "approaching":
      return (
        <span className="inline-flex items-center rounded-[2px] bg-hema-tint px-1.5 py-0.5 text-meta font-semibold text-hema">
          Within 30 days
        </span>
      );
    case "upcoming":
      return (
        <span className="inline-flex items-center rounded-[2px] border border-rule px-1.5 py-0.5 text-meta text-ink-2">
          Within 60 days
        </span>
      );
    case "good_standing":
      return (
        <span className="inline-flex items-center rounded-[2px] px-1 text-meta text-ink-3">
          Current
        </span>
      );
    default:
      return null;
  }
}
