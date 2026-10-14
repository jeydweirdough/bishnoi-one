import { ChevronRight } from "lucide-react";
import Link from "next/link";
import type { Alert } from "../lib/types";

const MARK: Record<Alert["tone"], string> = {
  critical: "border-eosin bg-eosin text-white",
  warning: "border-eosin text-eosin",
  info: "border-rule-strong text-ink-2",
};

/** What needs someone, worst first: a count, a few examples, and where to go. */
export function AlertList({ alerts, compact = false }: { alerts: Alert[]; compact?: boolean }) {
  if (alerts.length === 0) {
    return <p className="py-4 text-sm text-ink-2">No alerts. Stock is above reorder levels, no batches are expiring soon, and no documents are pending.</p>;
  }
  const order = { critical: 0, warning: 1, info: 2 };
  return (
    <ul className="mt-1 divide-y divide-rule">
      {[...alerts]
        .sort((a, b) => order[a.tone] - order[b.tone])
        .map((a) => (
          <li key={a.key} className="relative py-2.5">
            <Link href={a.href} className="flex items-start gap-3 after:absolute after:inset-0 hover:[&_span.title]:text-ink">
              <span className={`mt-0.5 inline-flex h-6 min-w-8 shrink-0 items-center justify-center rounded-md border px-1.5 text-meta font-semibold tabular-nums ${MARK[a.tone]}`}>
                {a.count}
              </span>
              <span className="min-w-0 flex-1">
                <span className="title block text-sm font-semibold text-ink">{a.title}</span>
                {a.examples.length > 0 && (
                  <span className="block text-meta text-ink-3">
                    {(compact ? a.examples.slice(0, 2) : a.examples).join(" · ")}
                    {a.count > (compact ? 2 : a.examples.length) && " …"}
                  </span>
                )}
              </span>
              <ChevronRight className="mt-1 size-4 shrink-0 text-ink-3" aria-hidden />
            </Link>
          </li>
        ))}
    </ul>
  );
}
