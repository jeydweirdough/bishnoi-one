import { CUSTOMER_STATUSES, QUOTE_STATES } from "@/src/modules/pharmacy/platform/lib/labels";
import type { CustomerStatus, Quote } from "@/src/modules/pharmacy/platform/lib/types";

// Status is printed in ink, never coloured: dashed = lead (not yet a customer),
// solid = active, outlined = inactive.
const statusStyle: Record<CustomerStatus, string> = {
  lead: "border border-dashed border-ink-2 text-ink-2",
  active: "border border-ink bg-ink text-white",
  inactive: "border border-rule-strong text-ink-3",
};

export function StatusMark({ status }: { status: CustomerStatus }) {
  return (
    <span
      className={`inline-flex h-5 items-center rounded-[2px] px-1.5 text-stamp uppercase ${statusStyle[status]}`}
    >
      {CUSTOMER_STATUSES[status]}
    </span>
  );
}

// A quote's state. Most quotes are ready, so ready is the quiet one; the
// exceptions carry the weight: waiting on Finance is dashed, and rejected, which
// the rep has to act on, is a flag.
export function QuoteStateMark({ state }: { state: Quote["state"] }) {
  if (state === "rejected") return <Flag letter="!">{QUOTE_STATES.rejected}</Flag>;
  if (state === "ready") {
    return <span className="text-stamp whitespace-nowrap text-ink-3 uppercase">{QUOTE_STATES.ready}</span>;
  }
  return (
    <span className="inline-flex h-5 shrink-0 items-center rounded-[2px] border border-dashed border-ink-2 px-1.5 text-stamp whitespace-nowrap text-ink-2 uppercase">
      {QUOTE_STATES.waiting}
    </span>
  );
}

/** Eosin, a boxed letter and words. The only place the second colour appears. */
export function Flag({ letter, children }: { letter: string; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-meta font-semibold text-eosin">
      <span
        aria-hidden
        className="inline-flex size-[18px] items-center justify-center rounded-[2px] border border-eosin text-stamp leading-none"
      >
        {letter}
      </span>
      {children}
    </span>
  );
}
