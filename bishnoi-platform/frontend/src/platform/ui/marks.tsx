import { CUSTOMER_STATUSES, QUOTE_STATES } from "../lib/labels";
import type { CustomerStatus, Quote } from "../lib/types";

// Status as a pill, and always in words: dashed = lead (not yet a customer),
// sage = active, grey = inactive.
const statusStyle: Record<CustomerStatus, string> = {
  lead: "border border-dashed border-ink-2 text-ink-2",
  active: "border border-transparent bg-[#e6f2e1] text-[#3f6f35]",
  inactive: "border border-transparent bg-[#f0f0ee] text-ink-3",
};

export function StatusMark({ status }: { status: CustomerStatus }) {
  return (
    <span
      className={`inline-flex h-6 items-center rounded-full px-2.5 text-meta font-medium whitespace-nowrap ${statusStyle[status]}`}
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
    return <span className="inline-flex h-6 items-center rounded-full bg-[#e6f2e1] px-2.5 text-meta font-medium whitespace-nowrap text-[#3f6f35]">{QUOTE_STATES.ready}</span>;
  }
  return (
    <span className="inline-flex h-6 shrink-0 items-center rounded-full border border-dashed border-ink-2 px-2.5 text-meta font-medium whitespace-nowrap text-ink-2">
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
        className="inline-flex size-[18px] items-center justify-center rounded-full border border-eosin text-stamp leading-none"
      >
        {letter}
      </span>
      {children}
    </span>
  );
}
