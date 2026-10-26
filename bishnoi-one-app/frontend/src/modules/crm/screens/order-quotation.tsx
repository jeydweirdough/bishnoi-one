import { CheckCircle2, Circle, Clock, MessageCircle } from "lucide-react";
import { ApiError, api } from "@/src/platform/lib/api";
import { COMPANY_HEADER } from "@/src/platform/lib/session-cookie";
import { fallbackFormat as fmt } from "@/src/platform/lib/format";
import { EmptyDrawing } from "@/src/platform/ui/empty-drawings";
import { PrintButton } from "@/src/modules/crm/components/print-button";
import { AutoRefresh } from "@/src/modules/crm/components/quotes/auto-refresh";
import { CodeQuotation } from "@/src/modules/crm/quote-templates/code-page";
import { DesignedQuotation } from "@/src/modules/crm/quote-templates/designed";
import type { QuoteDocument } from "@/src/modules/crm/quote-templates/types";

export const metadata = { title: "Your quotation", robots: { index: false, follow: false } };

type Step = { label: string; done: boolean };
type Standard = {
  letterhead: { name: string; address: string | null; tin: string | null; contact: string | null };
  customerName: string;
  createdAt: string | null;
  validUntil: string | null;
  priceTypeName: string;
  rx: boolean;
  lines: { name: string; code: string | null; quantity: number; unit: string | null; unitPriceCentavos: number | null; totalCentavos: number | null }[];
  grossCentavos: number;
  discountCentavos: number;
  totalCentavos: number;
  terms: string | null;
};
type Quotation = {
  number: string;
  rep: string;
  orderedAt: string | null;
  state: "waiting" | "clarify" | "rejected" | "ready";
  steps: Step[];
  document?: QuoteDocument & { html?: string };
  standard?: Standard;
};
type Params = Promise<{ company: string; token: string }>;

const paper = "mx-auto max-w-[210mm] bg-white px-[14mm] py-[12mm] text-[10.5pt] leading-snug text-black shadow-sm print:my-0 print:max-w-none print:p-0 print:shadow-none";

/**
 * The customer's quotation, opened from their order link after they order (decided 2026-10-26):
 * while it's reviewed, a short checklist of what it waits on (refreshing by itself); once nothing
 * is pending, the quotation with its prices, to print or save as PDF. The link is the key.
 */
export default async function OrderQuotationPage({ params }: { params: Params }) {
  const { company, token } = await params;
  let q: Quotation | null = null;
  let gone = "";
  try {
    q = await api.get<Quotation>(`/public/quote-links/${encodeURIComponent(token)}/quotation`, { [COMPANY_HEADER]: company });
  } catch (e) {
    gone = e instanceof ApiError && typeof e.detail === "string" ? e.detail : "Your quotation can't be opened right now. Try again in a moment.";
  }

  if (!q)
    return (
      <main className="min-h-dvh bg-bench px-4 py-8">
        <section className="mx-auto mt-16 max-w-md rounded-sheet border border-rule bg-sheet p-8 text-center">
          <EmptyDrawing icon="quotes" className="mx-auto h-[92px] w-[120px]" />
          <h1 className="mt-3 text-heading text-ink">No quotation here</h1>
          <p className="mt-1 text-sm text-ink-2">{gone}</p>
        </section>
      </main>
    );

  const first = q.rep.split(" ")[0];
  return (
    <main className="min-h-dvh bg-bench px-4 py-8 sm:px-8 print:bg-white print:p-0">
      <div className="mx-auto max-w-[210mm]">
        <header className="mb-5 flex flex-wrap items-end justify-between gap-3 print:hidden">
          <div>
            <p className="text-caps text-ink-3 uppercase">Quotation {q.number}</p>
            <h1 className="mt-1 text-[1.75rem] leading-tight font-semibold text-ink">{q.state === "ready" ? "Your quotation is ready" : "Your quotation"}</h1>
            <p className="mt-1 text-sm text-ink-2">From {q.rep}, your medical representative.</p>
          </div>
          {q.state === "ready" && <PrintButton />}
        </header>

        {q.state === "ready" ? (
          q.document?.html ? (
            <CodeQuotation html={q.document.html} title={`Quotation ${q.number}`} />
          ) : q.document ? (
            <article className={paper}>
              <DesignedQuotation doc={q.document} fmt={fmt} />
            </article>
          ) : q.standard ? (
            <StandardQuotation number={q.number} s={q.standard} />
          ) : null
        ) : (
          <section className="rounded-sheet border border-rule bg-sheet p-5 sm:p-6">
            {q.state === "waiting" && (
              <>
                <p className="flex items-center gap-2 font-semibold text-ink">
                  <Clock className="size-5 text-due-today" aria-hidden />
                  Being reviewed
                </p>
                <p className="mt-1 text-sm text-ink-2">Your quotation with prices opens here as soon as these are done. Keep this page; it updates by itself.</p>
                <ul className="mt-4 space-y-2">
                  {q.steps.map((s) => (
                    <li key={s.label} className={`flex items-center gap-2.5 text-sm ${s.done ? "text-ink" : "text-ink-2"}`}>
                      {s.done ? <CheckCircle2 className="size-5 text-sage-deep" aria-hidden /> : <Circle className="size-5 text-ink-3" aria-hidden />}
                      {s.label}
                    </li>
                  ))}
                </ul>
                <AutoRefresh seconds={30} />
              </>
            )}
            {(q.state === "clarify" || q.state === "rejected") && (
              <>
                <p className="flex items-center gap-2 font-semibold text-ink">
                  <MessageCircle className="size-5 text-due-today" aria-hidden />
                  {first} will contact you
                </p>
                <p className="mt-1 text-sm text-ink-2">
                  {q.state === "clarify" ? "The pharmacist needs something more about your prescription." : "This order needs a change before it can be quoted."} {first} will reach you to sort it out.
                </p>
              </>
            )}
          </section>
        )}
      </div>
    </main>
  );
}

/** The quotation when the company has no template for it: letterhead, lines with prices, total. */
function StandardQuotation({ number, s }: { number: string; s: Standard }) {
  const caption = "text-[8.5pt] font-semibold tracking-wide text-neutral-600 uppercase";
  return (
    <article className={paper}>
      <header className="flex items-start justify-between gap-8 border-b-2 border-black pb-4">
        <div>
          <p className="text-[16pt] font-bold">{s.letterhead.name}</p>
          {s.letterhead.address && <p className="whitespace-pre-line">{s.letterhead.address}</p>}
          {s.letterhead.tin && <p>TIN {s.letterhead.tin}</p>}
          {s.letterhead.contact && <p>{s.letterhead.contact}</p>}
        </div>
        <div className="text-right">
          <p className="text-[18pt] font-bold tracking-wide">QUOTATION</p>
          <p className="font-semibold">No. {number}</p>
          {s.createdAt && <p>Date: {fmt.dateLabel(s.createdAt.slice(0, 10))}</p>}
          {s.validUntil && <p>Valid until: {fmt.dateLabel(s.validUntil)}</p>}
        </div>
      </header>
      <section className="mt-4">
        <p className={caption}>Quoted to</p>
        <p className="font-semibold">{s.customerName}</p>
        <p>
          {s.priceTypeName}
          {s.rx ? " (with prescription)" : ""}
        </p>
      </section>
      <table className="mt-5 w-full border-collapse">
        <thead>
          <tr className="border-y border-black text-left">
            <th className="py-1.5 pr-2">Product</th>
            <th className="py-1.5 pr-2 text-right">Qty</th>
            <th className="py-1.5 pr-2 text-right">Unit price</th>
            <th className="py-1.5 text-right">Amount</th>
          </tr>
        </thead>
        <tbody>
          {s.lines.map((l, i) => (
            <tr key={i} className="border-b border-neutral-300">
              <td className="py-1.5 pr-2">
                {l.name}
                {l.code && <span className="text-neutral-500"> · {l.code}</span>}
              </td>
              <td className="py-1.5 pr-2 text-right tabular-nums">
                {l.quantity} {l.unit ?? ""}
              </td>
              <td className="py-1.5 pr-2 text-right tabular-nums">{l.unitPriceCentavos != null ? fmt.peso(l.unitPriceCentavos) : ""}</td>
              <td className="py-1.5 text-right tabular-nums">{l.totalCentavos != null ? fmt.peso(l.totalCentavos) : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 ml-auto w-64 space-y-1 tabular-nums">
        {s.discountCentavos > 0 && (
          <>
            <p className="flex justify-between">
              <span>Subtotal</span>
              <span>{fmt.peso(s.grossCentavos)}</span>
            </p>
            <p className="flex justify-between">
              <span>Discount</span>
              <span>−{fmt.peso(s.discountCentavos)}</span>
            </p>
          </>
        )}
        <p className="flex justify-between border-t-2 border-black pt-1 text-[12pt] font-bold">
          <span>Total</span>
          <span>{fmt.peso(s.totalCentavos)}</span>
        </p>
      </div>
      {s.terms && <p className="mt-6 text-[9pt] whitespace-pre-line text-neutral-700">{s.terms}</p>}
    </article>
  );
}
