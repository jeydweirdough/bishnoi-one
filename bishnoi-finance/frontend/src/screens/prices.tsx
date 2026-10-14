import { ApiError, api, getCompanyMe } from "@/src/platform/lib/api";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { DecidePrice, DecideQuote } from "../prices/decide";
import type { Waiting, WaitingPrice, WaitingQuote } from "../prices/types";

// Price approvals: every product's price is Finance's. What waits is read from
// the CRM each time; a decision goes straight back to it.

function Change({ p, fmt }: { p: WaitingPrice; fmt: Format }) {
  if (p.proposedAmountCentavos === 0) {
    return <span className="text-sm font-semibold text-danger">Take this price away{p.currentAmountCentavos ? ` (now ${fmt.peso(p.currentAmountCentavos)})` : ""}</span>;
  }
  const now = p.currentAmountCentavos;
  const to = p.proposedAmountCentavos ?? 0;
  const change = now ? (to - now) / now : null;
  return (
    <span className="text-right">
      <span className="block text-sm font-semibold tabular-nums">
        {now ? <span className="font-normal text-ink-3 line-through">{fmt.peso(now)}</span> : <span className="font-normal text-ink-3">New</span>} → {fmt.peso(to)}
      </span>
      {change !== null && change !== 0 && (
        <span className={`block text-meta tabular-nums ${change < 0 ? "text-danger" : "text-ink-3"}`}>
          {change > 0 ? "+" : ""}
          {(change * 100).toFixed(1)}%
        </span>
      )}
    </span>
  );
}

/** How a requested price sits against the SRP Finance set. */
function AgainstSrp({ unit, srp, fmt }: { unit: number; srp: number | null; fmt: Format }) {
  if (!srp) return <span className="text-ink-3">No SRP</span>;
  const off = (srp - unit) / srp;
  if (off <= 0) return <span className="text-ink-3">At or above SRP ({fmt.peso(srp)})</span>;
  return (
    <span className={off >= 0.2 ? "font-medium text-danger" : "text-ink-2"}>
      {(off * 100).toFixed(1)}% below SRP ({fmt.peso(srp)})
    </span>
  );
}

function QuoteRow({ q, fmt, canApprove }: { q: WaitingQuote; fmt: Format; canApprove: boolean }) {
  return (
    <li className="space-y-3 px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <div className="min-w-0">
          <p className="text-sm font-semibold">
            {q.url ? (
              <a href={q.url} target="_blank" rel="noopener" className="underline-offset-2 hover:underline">
                {q.number}
              </a>
            ) : (
              q.number
            )}
            <span className="font-normal text-ink-2"> · {q.customerName}</span>
          </p>
          <p className="text-meta text-ink-3">
            {q.repName} · {q.teamName} · {q.priceTypeName} · {fmt.whenLabel(q.createdAt)}
          </p>
        </div>
        <p className="text-right">
          <span className="block text-sm font-semibold tabular-nums">{fmt.peso(q.totalCentavos)}</span>
          {q.grossCentavos > q.totalCentavos && <span className="block text-meta text-ink-3">list {fmt.peso(q.grossCentavos)}</span>}
        </p>
      </div>
      {q.notes && <p className="rounded-md bg-bench px-3 py-2 text-meta text-ink-2">Why the rep asked: {q.notes}</p>}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-rule text-left text-meta text-ink-3">
            <th scope="col" className="py-1.5 font-medium">Product</th>
            <th scope="col" className="py-1.5 text-right font-medium">Qty</th>
            <th scope="col" className="py-1.5 text-right font-medium">Requested each</th>
            <th scope="col" className="hidden py-1.5 pl-4 font-medium sm:table-cell">Against SRP</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {q.lines.map((l, i) => (
            <tr key={i}>
              <td className="py-1.5">
                {l.productName} {l.productCode && <span className="text-meta text-ink-3">{l.productCode}</span>}
                <span className="block text-meta sm:hidden">
                  <AgainstSrp unit={l.unitPriceCentavos} srp={l.srpCentavos} fmt={fmt} />
                </span>
              </td>
              <td className="py-1.5 text-right tabular-nums">{l.quantity}</td>
              <td className="py-1.5 text-right tabular-nums">{fmt.peso(l.unitPriceCentavos)}</td>
              <td className="hidden py-1.5 pl-4 text-meta sm:table-cell">
                <AgainstSrp unit={l.unitPriceCentavos} srp={l.srpCentavos} fmt={fmt} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {canApprove && <DecideQuote id={q.id} number={q.number} />}
    </li>
  );
}

export default async function PricesPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  let waiting: Waiting | null = null;
  let trouble: string | null = null;
  try {
    waiting = await api.get<Waiting>("/finance/prices/waiting");
  } catch (e) {
    // The CRM keeps what waits: when it can't be reached, say so here, not on an error page.
    if (!(e instanceof ApiError) || e.status !== 409) throw e;
    trouble = e.message;
  }
  return (
    <>
      <PageHeader title="Price approvals">
        Every product&apos;s price is Finance&apos;s. A price a manager sets in the CRM, and a quote at a price a rep asked for, wait here: salespeople don&apos;t
        see the price, and the quote doesn&apos;t go out, until you approve it.
      </PageHeader>
      {trouble || !waiting ? (
        <Sheet>
          <Empty title="The CRM can't be read just now" icon="pricing">
            {trouble}
          </Empty>
        </Sheet>
      ) : (
        <>
          <Sheet className="mb-6">
            <h2 className="border-b border-rule px-5 py-3 text-sm font-semibold">
              Prices set by managers <span className="font-normal text-ink-3">· {waiting.prices.length}</span>
            </h2>
            {waiting.prices.length === 0 ? (
              <Empty title="No prices waiting" icon="pricing">
                A Doctor&apos;s, Patient&apos;s or Special price a manager sets in the CRM shows here until you decide it.
              </Empty>
            ) : (
              <ul className="divide-y divide-rule">
                {waiting.prices.map((p) => (
                  <li key={p.id} className="flex flex-wrap items-center gap-x-4 gap-y-3 px-5 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold">
                        {p.productName}
                        <span className="font-normal text-ink-2">
                          {" "}
                          · {p.priceTypeName} · {p.unit}
                        </span>
                      </p>
                      <p className="truncate text-meta text-ink-3">
                        {p.productCode} · {p.teamName} · asked by {p.submittedByName}
                        {p.submittedAt && `, ${fmt.whenLabel(p.submittedAt)}`}
                      </p>
                    </div>
                    <Change p={p} fmt={fmt} />
                    {waiting.canApprove && <DecidePrice price={p} />}
                  </li>
                ))}
              </ul>
            )}
          </Sheet>
          <Sheet>
            <h2 className="border-b border-rule px-5 py-3 text-sm font-semibold">
              Quotes at a requested price <span className="font-normal text-ink-3">· {waiting.quotes.length}</span>
            </h2>
            {waiting.quotes.length === 0 ? (
              <Empty title="No quotes waiting" icon="quotes">
                A quote where a rep asked for a price of their own waits here, oldest first, before it can go to the customer.
              </Empty>
            ) : (
              <ul className="divide-y divide-rule">
                {waiting.quotes.map((q) => (
                  <QuoteRow key={q.id} q={q} fmt={fmt} canApprove={waiting.canApprove} />
                ))}
              </ul>
            )}
          </Sheet>
          {!waiting.canApprove && <p className="mt-3 text-meta text-ink-3">You can see these; deciding them needs the Approve permission for product prices.</p>}
        </>
      )}
    </>
  );
}
