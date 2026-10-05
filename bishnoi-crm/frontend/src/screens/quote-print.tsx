import Link from "next/link";
import { FileSpreadsheet } from "lucide-react";
import { PrintButton } from "../components/print-button";
import { DesignedQuotation } from "../quote-templates/designed";
import type { QuoteDocument } from "../quote-templates/types";
import { buttonClass, LinkButton } from "@/src/platform/ui/button";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { Quote } from "@/src/platform/lib/types";

type Letterhead = { name: string; address: string | null; tin: string | null; contact: string | null };
type Params = Promise<{ id: string }>;
type Search = Promise<Record<string, string | string[] | undefined>>;
type Fitting = { items: { id: string; name: string; kind: "form" | "excel" }[] };

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    return { title: `Quotation ${(await load<Quote>(`/quotes/${enc(id)}`)).number}` };
  } catch {
    return { title: "Quotation" };
  }
}

const caption = "text-[8.5pt] font-semibold tracking-wide text-neutral-600 uppercase";
const paper =
  "mx-auto my-8 max-w-[210mm] bg-white px-[16mm] py-[14mm] text-[10.5pt] leading-snug text-black shadow-sm print:my-0 print:max-w-none print:p-0 print:shadow-none";

/** A quote on paper. With a quotation template set up for it (Settings,
 *  Quotation templates), that template: designed ones print from here,
 *  uploaded Excel forms download filled in. Otherwise the standard quotation.
 *  Outside the app's frame, so only the document prints. */
export default async function QuotePrintPage({ params, searchParams }: { params: Params; searchParams: Search }) {
  const [{ id }, search] = await Promise.all([params, searchParams]);
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const [quote, fitting] = await Promise.all([load<Quote>(`/quotes/${enc(id)}`), load<Fitting>(`/quotes/${enc(id)}/templates`)]);
  const wanted = typeof search.template === "string" ? search.template : undefined;
  const template = wanted === "standard" ? null : (fitting.items.find((t) => t.id === wanted) ?? fitting.items[0] ?? null);
  const doc = template ? await load<QuoteDocument>(`/quotes/${enc(id)}/document?template=${enc(template.id)}`) : null;
  const choices = [...fitting.items, { id: "standard", name: "Standard quotation", kind: "form" as const }];
  const excelHref = template?.kind === "excel" ? `/quotes/${id}/document?template=${template.id}` : null;

  return (
    <div className="min-h-screen bg-bench print:bg-white">
      <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-rule bg-sheet px-6 py-3 print:hidden">
        <LinkButton href={`/quotes/${id}`} variant="quiet">
          Back to the quote
        </LinkButton>
        {choices.length > 1 && (
          <nav aria-label="Quotation template" className="inline-flex flex-wrap rounded-[6px] border border-rule-strong bg-sheet p-0.5">
            {choices.map((c) => {
              const on = (template?.id ?? "standard") === c.id;
              return (
                <Link
                  key={c.id}
                  href={`/print/quotes/${id}?template=${c.id}`}
                  aria-current={on ? "page" : undefined}
                  className={`rounded-[4px] px-3 py-1 text-meta ${on ? "bg-hema-tint font-semibold text-ink" : "text-ink-2 hover:text-ink"}`}
                >
                  {c.name}
                  {c.kind === "excel" ? " (Excel)" : ""}
                </Link>
              );
            })}
          </nav>
        )}
        <div className="flex gap-2">
          {excelHref && (
            <a href={excelHref} download className={buttonClass("primary")}>
              <FileSpreadsheet className="size-4" aria-hidden />
              Download Excel
            </a>
          )}
          {!excelHref && <PrintButton auto={search.auto === "1"} />}
        </div>
      </div>

      {doc && template?.kind === "excel" ? (
        <section className="mx-auto my-8 max-w-[210mm] rounded-[4px] bg-sheet px-6 py-5 shadow-sm">
          <h1 className="text-heading text-ink">{doc.template.name}</h1>
          <p className="mt-1 text-sm text-ink-2">
            This quotation is your Excel form, filled in: control no. <strong>{doc.controlNumber}</strong>, {doc.lines.length}{" "}
            {doc.lines.length === 1 ? "product" : "products"}, grand total {fmt.peso(Math.round(doc.total * 100))}
            {doc.template.hasSignature ? ", signed with the e-signature" : ""}.
          </p>
          <a href={excelHref!} download className={`${buttonClass("primary")} mt-4`}>
            <FileSpreadsheet className="size-4" aria-hidden />
            Download Excel
          </a>
          <p className="mt-3 text-meta text-ink-3">Open it in Excel to print it or save it as PDF before sending it to the patient.</p>
        </section>
      ) : doc ? (
        <article className={paper}>
          <DesignedQuotation doc={doc} fmt={fmt} />
        </article>
      ) : (
        <StandardQuotation quote={quote} fmt={fmt} />
      )}
    </div>
  );
}

/** The quotation when no template is set up for the quote. */
async function StandardQuotation({ quote, fmt }: { quote: Quote; fmt: Format }) {
  const head = await load<Letterhead>("/quote-letterhead");
  const letter = quote.letter;
  const discounted = quote.promoDiscountCentavos + quote.discountCentavos;
  return (
    <article className={paper}>
      <header className="flex items-start justify-between gap-8 border-b-2 border-black pb-4">
        <div>
          <p className="text-[16pt] font-bold">{head.name}</p>
          {head.address && <p className="whitespace-pre-line">{head.address}</p>}
          {head.tin && <p>TIN {head.tin}</p>}
          {head.contact && <p>{head.contact}</p>}
        </div>
        <div className="text-right">
          <p className="text-[18pt] font-bold tracking-wide">QUOTATION</p>
          <p className="font-semibold">No. {quote.number}</p>
          <p>Date: {fmt.dateLabel(quote.createdAt.slice(0, 10))}</p>
          {quote.validUntil && <p>Valid until: {fmt.dateLabel(quote.validUntil)}</p>}
        </div>
      </header>

      <section className="mt-4 grid grid-cols-2 gap-8">
        <div>
          <p className={caption}>Quoted to</p>
          <p className="font-semibold">{quote.customerName}</p>
          {quote.contact && quote.company && <p>{quote.company.name}</p>}
        </div>
        <div>
          <p className={caption}>Details</p>
          <p>
            Price: {quote.priceTypeName}
            {quote.rx ? " (with prescription)" : ""}
          </p>
          <p>Team: {quote.teamName}</p>
          {quote.owner && <p>Sales representative: {quote.owner.name}</p>}
          {letter && (
            <p>
              Paid by: {quote.payerName} guarantee letter no. {letter.number}, covering {fmt.peso(letter.amountCentavos)}
            </p>
          )}
        </div>
      </section>

      <table className="mt-5 w-full border-collapse">
        <thead>
          <tr className="border-y border-black text-left text-[9pt]">
            <th scope="col" className="w-8 py-1.5 pr-2 font-semibold">No.</th>
            <th scope="col" className="py-1.5 pr-2 font-semibold">Product</th>
            <th scope="col" className="px-2 py-1.5 text-right font-semibold">Qty</th>
            <th scope="col" className="px-2 py-1.5 text-right font-semibold">Unit price</th>
            <th scope="col" className="px-2 py-1.5 text-right font-semibold">Discount</th>
            <th scope="col" className="py-1.5 pl-2 text-right font-semibold">Amount</th>
          </tr>
        </thead>
        <tbody>
          {quote.lines.map((line, i) => {
            const off = (line.promoDiscountCentavos ?? 0) + (line.discountCentavos ?? 0) + (line.volumeDiscountCentavos ?? 0);
            return (
              <tr key={`${line.productId}:${i}`} className="break-inside-avoid border-b border-neutral-300 align-top">
                <td className="py-1.5 pr-2 tabular-nums">{i + 1}</td>
                <td className="py-1.5 pr-2">
                  <span className="font-medium">{line.productName}</span>
                  <span className="block text-[9pt] text-neutral-600">
                    {line.productCode} · {line.unit}
                    {line.promoName ? ` · ${line.promoName}` : ""}
                  </span>
                  {line.contents && <span className="block text-[9pt] text-neutral-600">{line.contents}</span>}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums">
                  {line.quantity}
                  {line.freeQuantity > 0 && <span className="block text-[9pt]">+{line.freeQuantity} free</span>}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums">{fmt.peso(line.unitPriceCentavos)}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{off > 0 ? `−${fmt.peso(off)}` : ""}</td>
                <td className="py-1.5 pl-2 text-right font-medium tabular-nums">{fmt.peso(line.totalCentavos)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <section className="mt-3 ml-auto w-[95mm] break-inside-avoid space-y-0.5">
        <p className="flex justify-between">
          <span>Gross amount</span>
          <span className="tabular-nums">{fmt.peso(quote.grossCentavos)}</span>
        </p>
        {discounted > 0 && (
          <p className="flex justify-between">
            <span>Less discounts</span>
            <span className="tabular-nums">−{fmt.peso(discounted)}</span>
          </p>
        )}
        {quote.tax ? (
          <>
            {quote.tax.summary
              .filter((row) => row.amountCentavos > 0)
              .map((row) => (
                <p key={row.key} className="flex justify-between text-[9.5pt]">
                  <span>{row.label}</span>
                  <span className="tabular-nums">{fmt.peso(row.amountCentavos)}</span>
                </p>
              ))}
            <p className="flex justify-between border-t border-black pt-1 text-[12pt] font-bold">
              <span>Total amount due{quote.tax.pricesIncludeTax ? " (VAT inclusive)" : ""}</span>
              <span className="tabular-nums">{fmt.peso(quote.tax.totalDueCentavos)}</span>
            </p>
          </>
        ) : (
          <p className="flex justify-between border-t border-black pt-1 text-[12pt] font-bold">
            <span>Total amount</span>
            <span className="tabular-nums">{fmt.peso(quote.totalCentavos)}</span>
          </p>
        )}
      </section>

      {(quote.terms || quote.notes) && (
        <section className="mt-6 break-inside-avoid space-y-3">
          {quote.terms && (
            <div>
              <p className={caption}>Terms and conditions</p>
              <p className="whitespace-pre-line">{quote.terms}</p>
            </div>
          )}
          {quote.notes && (
            <div>
              <p className={caption}>Remarks</p>
              <p className="whitespace-pre-line">{quote.notes}</p>
            </div>
          )}
        </section>
      )}

      <section className="mt-12 grid break-inside-avoid grid-cols-3 gap-8">
        {[
          ["Prepared by", quote.owner?.name ?? quote.createdBy.name],
          ["Approved by", quote.approval.by?.name ?? ""],
          ["Accepted by (customer)", ""],
        ].map(([role, name]) => (
          <div key={role}>
            <p className="text-[9pt] text-neutral-600">{role}</p>
            <p className="mt-10 border-t border-black pt-1 text-center font-medium">{name || " "}</p>
            <p className="text-center text-[8.5pt] text-neutral-600">Signature over printed name and date</p>
          </div>
        ))}
      </section>

      <footer className="mt-8 border-t border-neutral-300 pt-2 text-center text-[8.5pt] text-neutral-600">
        This quotation is not an official receipt or invoice.
        {quote.validUntil ? ` Prices are valid until ${fmt.dateLabel(quote.validUntil)}.` : ""}
      </footer>
    </article>
  );
}
