import { Plus } from "lucide-react";
import Link from "next/link";
import { DeleteQuote } from "./delete-quote";
import { LinkButton } from "@/src/platform/ui/button";
import { QuoteStateMark } from "@/src/platform/ui/marks";
import { orgFormat } from "@/src/platform/lib/org";
import type { Quote } from "@/src/platform/lib/types";

/** A company's or contact's quotes, newest first. `customerHref` is its page. */
export async function QuotesPanel({ customerHref, quotes, canAdd, showWho = false }: { customerHref: string; quotes: Quote[]; canAdd: boolean; showWho?: boolean }) {
  const fmt = await orgFormat();
  const today = fmt.todayKey();
  return (
    <div>
      {quotes.length === 0 ? (
        <p className="py-3 text-meta text-ink-3">No quotes yet.</p>
      ) : (
        <ul className="divide-y divide-rule">
          {quotes.map((q) => (
            <li key={q.id} className="flex items-start justify-between gap-3 py-3">
              <div className="min-w-0">
                <Link href={`/quotes/${q.id}`} className="font-semibold text-hema hover:underline">
                  {q.number}
                </Link>
                <p className="text-meta text-ink-3">
                  {fmt.whenLabel(q.createdAt, today)} · {q.priceTypeName}
                  {showWho && q.contact && ` · ${q.contact.name}`}
                  {q.rx && " · Rx"}
                  {q.payerName && ` · ${q.payerName} letter`}
                </p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                <span className="font-semibold tabular-nums">{fmt.peso(q.totalCentavos)}</span>
                <QuoteStateMark state={q.state} />
                {/* Only the quotes this person may delete offer it, and the
                    answer comes from the API per quote — the same one the
                    quote's own page asks. */}
                {q.can.delete && (
                  <DeleteQuote id={q.id} number={q.number} stay size="sm" />
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {canAdd && (
        <LinkButton
          href={`${customerHref}/quotes/new`}
          size="sm"
          variant="quiet"
          className="mt-1 -ml-3"
          icon={<Plus className="size-4" aria-hidden />}
        >
          New quote
        </LinkButton>
      )}
    </div>
  );
}
