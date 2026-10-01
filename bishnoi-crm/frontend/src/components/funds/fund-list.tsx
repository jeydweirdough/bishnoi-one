import { Check } from "lucide-react";
import Link from "next/link";
import type { Format } from "@/src/platform/lib/format";
import type { FundRequest } from "./types";
import { TONE_CLASS, stepsOf, toneOf } from "./words";

/** Where a request is, as a tag: loud when it's the requester's move. */
export function FundStatusTag({ request }: { request: FundRequest }) {
  const overdue = request.status === "to_liquidate" && request.finance?.overdue;
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-meta font-medium whitespace-nowrap ${overdue ? "bg-danger-tint text-danger" : TONE_CLASS[toneOf(request.status)]}`}>
      {overdue ? "Liquidation overdue" : request.statusLabel}
    </span>
  );
}

/** The requests, newest first: what for, how much, and where each is. */
export function FundList({ items, fmt, showWho }: { items: FundRequest[]; fmt: Format; showWho: boolean }) {
  return (
    <ul className="divide-y divide-rule">
      {items.map((r) => (
        <li key={r.id}>
          <Link href={`/funds/${r.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3 hover:bg-bench/60">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">
                {r.purpose.name}
                {r.company && <span className="font-normal text-ink-2"> · {r.company.name}</span>}
              </p>
              <p className="truncate text-meta text-ink-3">
                {r.number}
                {showWho && ` · ${r.owner.name}`} · {fmt.whenLabel(r.createdAt)}
                {r.neededOn && ` · needed by ${fmt.dateLabel(r.neededOn)}`}
              </p>
            </div>
            <p className="text-sm font-semibold tabular-nums">{fmt.peso(r.approvedCentavos ?? r.amountCentavos)}</p>
            <FundStatusTag request={r} />
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Asked → Approved → Released → Liquidated → Settled, and where it is. */
export function FundSteps({ request }: { request: FundRequest }) {
  const steps = stepsOf(request);
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-2 text-meta" aria-label="Steps">
      {steps.map((s, i) => (
        <li key={s.label} className="flex items-center gap-2">
          {i > 0 && <span aria-hidden className={`h-px w-5 ${s.done || s.current ? "bg-hema" : "bg-rule-strong"}`} />}
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 ${
              s.done ? "bg-hema text-white" : s.current ? "border border-hema font-semibold text-hema" : "border border-rule-strong text-ink-3"
            }`}
            aria-current={s.current ? "step" : undefined}
          >
            {s.done && <Check className="size-3" aria-hidden />}
            {s.label}
          </span>
        </li>
      ))}
    </ol>
  );
}
