import { FileText } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Flag } from "@/src/platform/ui/marks";
import { Particulars, SectionTitle, Subheading, Sheet } from "@/src/platform/ui/sheet";
import { percent, type Format } from "@/src/platform/lib/format";
import { orgFormat } from "@/src/platform/lib/org";
import { APPROVAL_STATUSES, LETTER_STATUSES, PAYMENT_STATUSES, approvalReason } from "@/src/platform/lib/labels";
import type { CustomField, Quote, QuoteLine } from "@/src/platform/lib/types";
import { extraItems } from "./extra/extra-values";

function discountLabel(fmt: Format, line: QuoteLine) {
  if (!line.discountKind || !line.discountValue) return null;
  return line.discountKind === "percent" ? `${percent(line.discountValue)} off` : `${fmt.peso(line.discountValue)} off`;
}

function Decision({ fmt, label, by, at, note }: { fmt: Format; label: string; by: Quote["approval"]["by"]; at: string | null; note: string | null }) {
  return (
    <>
      <p className="font-semibold">{label}</p>
      {by && (
        <p className="text-meta text-ink-3">
          {by.name} · {fmt.whenLabel(at)}
        </p>
      )}
      {note && <p className="mt-1 whitespace-pre-line text-ink-2">“{note}”</p>}
    </>
  );
}

/** A quote as everyone reads it: lines, totals and where approval and payment stand. Each of the approver's actions sits in the part it decides. */
export async function QuoteView({
  quote,
  letterHref,
  customerHref,
  actions,
  fields = [],
}: {
  quote: Quote;
  /** The fields added to quotes (Settings → Forms), to show the values this one has. */
  fields?: CustomField[];
  letterHref: string;
  customerHref?: string;
  actions?: { approval?: ReactNode; letter?: ReactNode; payment?: ReactNode };
}) {
  const fmt = await orgFormat();
  const { approval, letter, payment } = quote;
  return (
    <div className="flex flex-col gap-5 lg:grid lg:grid-cols-[minmax(0,1fr)_23rem] lg:items-start">
      <div className="space-y-5">
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="products">Products</SectionTitle>
          <div className="mt-1 overflow-x-auto">
            <table className="w-full min-w-[36rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th scope="col" className="py-2 pr-3 font-semibold">Product</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Qty</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Each</th>
                  <th scope="col" className="px-3 py-2 font-semibold">Promo / discount</th>
                  <th scope="col" className="py-2 pl-3 text-right font-semibold">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {quote.lines.map((line, i) => (
                  <tr key={`${line.bundleId ?? ""}:${line.productId}:${i}`} className="align-top">
                    <td className="py-2.5 pr-3">
                      <span className="font-medium">{line.productName}</span>
                      <span className="block text-meta text-ink-3">
                        {line.productCode} · {line.unit}
                      </span>
                      {/* What a one-line bundle holds, so Dispatch packs the right box. */}
                      {line.contents && <span className="block text-meta text-ink-3">{line.contents}</span>}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {line.quantity}
                      {line.freeQuantity > 0 && <span className="block text-meta text-ink-2">+{line.freeQuantity} free</span>}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{fmt.peso(line.unitPriceCentavos)}</td>
                    <td className="px-3 py-2.5 text-meta text-ink-2">
                      {line.promoName && (
                        <span className="block">
                          {line.promoName}
                          {line.promoDiscountCentavos > 0 && ` (−${fmt.peso(line.promoDiscountCentavos)})`}
                        </span>
                      )}
                      {discountLabel(fmt, line) && (
                        <span className="block">
                          Extra {discountLabel(fmt, line)} (−{fmt.peso(line.discountCentavos)})
                        </span>
                      )}
                      {/* A set is its own deal; it takes no promo and no manual discount. */}
                      {line.bundleId && !line.contents && <span className="block">From {line.bundleName}</span>}
                      {!line.promoName && !discountLabel(fmt, line) && !line.bundleId && <span className="text-ink-3">—</span>}
                      {line.bundleId && line.contents && <span className="text-ink-3">The set price</span>}
                    </td>
                    <td className="py-2.5 pl-3 text-right font-medium tabular-nums">{fmt.peso(line.totalCentavos)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 ml-auto max-w-xs space-y-1 text-sm">
            <p className="flex justify-between text-ink-2">
              <span>List value</span>
              <span className="tabular-nums">{fmt.peso(quote.grossCentavos)}</span>
            </p>
            {quote.promoDiscountCentavos > 0 && (
              <p className="flex justify-between text-ink-2">
                <span>Promos</span>
                <span className="tabular-nums">−{fmt.peso(quote.promoDiscountCentavos)}</span>
              </p>
            )}
            {quote.discountCentavos > 0 && (
              <p className="flex justify-between text-ink-2">
                <span>Extra discounts</span>
                <span className="tabular-nums">−{fmt.peso(quote.discountCentavos)}</span>
              </p>
            )}
            <p className="flex justify-between border-t border-ink pt-1 text-base font-semibold">
              <span>Total</span>
              <span className="tabular-nums">{fmt.peso(quote.totalCentavos)}</span>
            </p>
          </div>
        </Sheet>

        <Sheet className="px-5 py-5">
          <SectionTitle icon="particulars">Particulars</SectionTitle>
          <div className="mt-2">
            <Particulars
              items={[
                [
                  "Customer",
                  customerHref ? (
                    <Link href={customerHref} className="text-hema hover:underline">
                      {quote.customerName}
                    </Link>
                  ) : (
                    quote.customerName
                  ),
                ],
                ["Team", quote.teamName],
                ["Price", `${quote.priceTypeName}${quote.rx ? " · with Rx" : ""}`],
                ["Paid by", quote.payerName ? `${quote.payerName}, with a guarantee letter` : "The customer"],
                ["Made by", `${quote.createdBy.name} · ${fmt.whenLabel(quote.createdAt)}`],
                ["Good until", quote.validUntil ? fmt.dateLabel(quote.validUntil) : null],
                ...extraItems(fmt, fields, quote.extra),
              ]}
            />
          </div>
          {quote.terms && (
            <div className="mt-5 border-t border-rule pt-4">
              <Subheading>Terms</Subheading>
              <p className="mt-1 whitespace-pre-line text-ink-2">{quote.terms}</p>
            </div>
          )}
          {quote.notes && (
            <div className="mt-5 border-t border-rule pt-4">
              <Subheading>Notes</Subheading>
              <p className="mt-1 whitespace-pre-line text-ink-2">{quote.notes}</p>
            </div>
          )}
        </Sheet>
      </div>

      <Sheet className="px-5 pt-4 pb-5">
        <SectionTitle icon="approvals">Approval & payment</SectionTitle>
        <div className="mt-1 divide-y divide-rule text-sm">
          <section className="py-3" aria-label="Approval">
            <h3 className="text-meta text-ink-3">Approval</h3>
            {approval.status === "none" ? (
              <p className="text-ink-2">Not needed</p>
            ) : (
              <>
                {approval.status === "pending" ? (
                  <Flag letter="!">Waiting for an approver</Flag>
                ) : (
                  <Decision fmt={fmt} label={APPROVAL_STATUSES[approval.status]} by={approval.by} at={approval.at} note={approval.note} />
                )}
                <ul className="mt-1 text-meta text-ink-3">
                  {approval.reasons.map((r) => (
                    <li key={r}>{approvalReason(r, quote)}</li>
                  ))}
                </ul>
                {actions?.approval}
              </>
            )}
          </section>

          {letter && (
            <section className="py-3" aria-label="Guarantee letter">
              <h3 className="text-meta text-ink-3">{quote.payerName} guarantee letter</h3>
              <p className="font-semibold">{letter.number}</p>
              <p className="text-ink-2">
                {fmt.dateLabel(letter.issuedOn)} · covers {fmt.peso(letter.amountCentavos)}
              </p>
              {letter.file && (
                <a href={letterHref} target="_blank" rel="noopener" className="mt-1 inline-flex items-center gap-1.5 text-hema hover:underline">
                  <FileText className="size-4" aria-hidden />
                  Open the letter <span className="text-meta text-ink-3">({Math.ceil(letter.file.size / 1024)} KB)</span>
                </a>
              )}
              <div className="mt-2">
                {letter.status === "pending" ? (
                  <Flag letter="!">Not checked yet</Flag>
                ) : (
                  <Decision fmt={fmt} label={LETTER_STATUSES[letter.status]} by={letter.by} at={letter.at} note={letter.note} />
                )}
              </div>
              {actions?.letter}
            </section>
          )}

          {letter && payment.status !== "none" && (
            <section className="py-3" aria-label="Letter payments">
              <h3 className="text-meta text-ink-3">Paid on the letter</h3>
              <p className="font-semibold">
                {PAYMENT_STATUSES[payment.status]} · {fmt.peso(payment.paidCentavos)} of {fmt.peso(letter.amountCentavos)}
              </p>
              {payment.payments.length > 0 && (
                <ul className="mt-1 space-y-0.5 text-meta text-ink-2">
                  {payment.payments.map((p) => (
                    <li key={p.id}>
                      {fmt.dateLabel(p.paidOn)} · {fmt.peso(p.amountCentavos)}
                      {p.reference && ` · ${p.reference}`}
                      {p.byName && <span className="text-ink-3"> · {p.byName}</span>}
                    </li>
                  ))}
                </ul>
              )}
              {actions?.payment}
            </section>
          )}
        </div>
      </Sheet>
    </div>
  );
}
