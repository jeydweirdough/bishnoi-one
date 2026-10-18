import { Avatar } from "@/src/platform/ui/avatar";
import { FileText } from "lucide-react";
import { PriceSource, RuleAdjustments, TaxSummary } from "./tax-summary";
import Link from "next/link";
import type { ReactNode } from "react";
import { Flag } from "@/src/platform/ui/marks";
import { Particulars, SectionTitle, Subheading, Sheet } from "@/src/platform/ui/sheet";
import { percent, type Format } from "@/src/platform/lib/format";
import { orgFormat } from "@/src/platform/lib/org";
import { APPROVAL_STATUSES, LETTER_STATUSES, PAYMENT_STATUSES, approvalReason } from "@/src/platform/lib/labels";
import type { CustomField, Quote, QuoteLine } from "@/src/platform/lib/types";
import { extraItems } from "./extra/extra-values";
import { AppliedPromo } from "./catalogue/promo-tag";

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

const PHARMACY_OUTCOMES = {
  verified: "Verified by the pharmacist",
  needs_clarification: "The pharmacist needs a clarification",
  rejected: "Rejected by the pharmacist",
} as const;

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
  actions?: { approval?: ReactNode; letter?: ReactNode; payment?: ReactNode; pharmacy?: ReactNode };
}) {
  const fmt = await orgFormat();
  const { approval, letter, payment, pharmacy } = quote;
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
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Unit price</th>
                  <th scope="col" className="px-3 py-2 font-semibold">Promo or discount</th>
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
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {fmt.peso(line.unitPriceCentavos)}
                      <PriceSource source={line.priceSource} />
                    </td>
                    <td className="px-3 py-2.5 text-meta text-ink-2">
                      {line.promoName && (
                        <span className="mb-1 block">
                          <AppliedPromo name={line.promoName} discountCentavos={line.promoDiscountCentavos} fmt={fmt} />
                        </span>
                      )}
                      {discountLabel(fmt, line) && (
                        <span className="block">
                          Extra {discountLabel(fmt, line)} (−{fmt.peso(line.discountCentavos)})
                        </span>
                      )}
                      <RuleAdjustments line={line} fmt={fmt} />
                      {/* A set is its own deal; it takes no promo and no manual discount. */}
                      {line.bundleId && !line.contents && <span className="block">From {line.bundleName}</span>}
                      {!line.promoName && !discountLabel(fmt, line) && !line.bundleId && !line.volumeDiscountCentavos && !line.surchargeCentavos && (
                        <span className="text-ink-3">—</span>
                      )}
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
              <span>Total value</span>
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
            {quote.tax && <TaxSummary tax={quote.tax} fmt={fmt} />}
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
                    <Link href={customerHref} className="text-ink hover:underline">
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
        <SectionTitle icon="approvals">Approval and payment</SectionTitle>
        <div className="mt-1 divide-y divide-rule text-sm">
          {pharmacy && (
            // Rx medicines: a pharmacist in Bishnoi One Pharmacy checks the prescription before the quote is ordered.
            <section className="py-3" aria-label="Pharmacist check">
              <h3 className="text-meta text-ink-3">Pharmacist check{pharmacy.number && ` · ${pharmacy.number}`}</h3>
              {pharmacy.outcome === "not_sent" ? (
                <Flag letter="!">Not sent to Pharmacy yet</Flag>
              ) : pharmacy.outcome === "waiting" ? (
                <Flag letter="!">Waiting for a pharmacist</Flag>
              ) : (
                <>
                  <p className="font-semibold">{PHARMACY_OUTCOMES[pharmacy.outcome]}</p>
                  {pharmacy.checkedBy && (
                    <p className="text-meta text-ink-3">
                      {pharmacy.checkedBy} · {fmt.whenLabel(pharmacy.checkedAt)}
                    </p>
                  )}
                  {pharmacy.note && <p className="mt-1 whitespace-pre-line text-ink-2">“{pharmacy.note}”</p>}
                </>
              )}
              {pharmacy.sent && (
                <p className="mt-1 text-meta text-ink-3">
                  {pharmacy.sent.prescriberName} · prescribed {fmt.dateLabel(pharmacy.sent.prescribedOn)} · sent by {pharmacy.sent.sentBy}
                </p>
              )}
              {pharmacy.outcome === "waiting" && pharmacy.blocking.length > 0 && (
                <ul className="mt-1 list-disc pl-4 text-meta text-ink-2">
                  {pharmacy.blocking.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              )}
              {pharmacy.error && <p className="mt-1 text-meta text-danger">{pharmacy.error} Showing the last answer.</p>}
              {actions?.pharmacy}
            </section>
          )}
          <section className="py-3" aria-label="Approval">
            <h3 className="text-meta text-ink-3">Approval</h3>
            {approval.status === "none" ? (
              <p className="text-ink-2">Not needed</p>
            ) : (
              <>
                {approval.status === "pending" ? (
                  <Waiting approvers={approval.approvers ?? []} />
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

          {(quote.prescriptions?.length ?? 0) > 0 && (
            <section className="py-3" aria-label="Prescription">
              <h3 className="text-meta text-ink-3">Prescription, from the customer</h3>
              <ul className="mt-1 space-y-1">
                {quote.prescriptions!.map((f) => (
                  <li key={f.n}>
                    <a href={`/quotes/${quote.id}/prescriptions/${f.n}`} target="_blank" rel="noopener" className="inline-flex items-center gap-1.5 text-ink hover:underline">
                      <FileText className="size-4" aria-hidden />
                      {f.name} <span className="text-meta text-ink-3">({Math.ceil(f.size / 1024)} KB)</span>
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {(quote.documents?.length ?? 0) > 0 && (
            <section className="py-3" aria-label="Documents">
              <h3 className="text-meta text-ink-3">Documents, from the customer</h3>
              <ul className="mt-1 space-y-1">
                {quote.documents!.map((f) => (
                  <li key={f.n}>
                    <a href={`/quotes/${quote.id}/documents/${f.n}`} target="_blank" rel="noopener" className="inline-flex items-center gap-1.5 text-ink hover:underline">
                      <FileText className="size-4" aria-hidden />
                      {f.label ?? f.name} <span className="text-meta text-ink-3">({f.name}, {Math.ceil(f.size / 1024)} KB)</span>
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {letter && (
            <section className="py-3" aria-label="Guarantee letter">
              <h3 className="text-meta text-ink-3">{quote.payerName} guarantee letter</h3>
              <p className="font-semibold">{letter.number}</p>
              <p className="text-ink-2">
                {fmt.dateLabel(letter.issuedOn)} · covers {fmt.peso(letter.amountCentavos)}
              </p>
              {letter.file && (
                <a href={letterHref} target="_blank" rel="noopener" className="mt-1 inline-flex items-center gap-1.5 text-ink hover:underline">
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

/** Who a quote waits on: "your approval" when it's you (the buttons follow), else the approvers by name. */
function Waiting({ approvers }: { approvers: { id: string; name: string; role: string; isMe?: boolean }[] }) {
  const mine = approvers.some((a) => a.isMe);
  const others = approvers.filter((a) => !a.isMe);
  const names = (list: typeof approvers) => (list.length === 1 ? list[0].name : list.length === 2 ? `${list[0].name} or ${list[1].name}` : `${list[0].name} or ${list.length - 1} others`);
  if (!approvers.length) {
    return (
      <>
        <Flag letter="!">Waiting for an approver</Flag>
        <p className="mt-1 text-meta text-ink-3">Nobody who can approve quotes reaches this team yet. An administrator gives a role Quotes → Approve.</p>
      </>
    );
  }
  return (
    <>
      <Flag letter="!">{mine ? "Waiting for your approval" : `Waiting for ${names(approvers)}`}</Flag>
      {mine ? (
        others.length > 0 && <p className="mt-1 text-meta text-ink-3">Also: {others.map((a) => a.name).join(", ")} can approve it.</p>
      ) : (
        <ul className="mt-1.5 space-y-1">
          {approvers.map((a) => (
            <li key={a.id} className="flex items-center gap-2 text-sm text-ink">
              <Avatar name={a.name} id={a.id} size="sm" />
              <span className="min-w-0">
                <span className="block truncate font-medium">{a.name}</span>
                <span className="block text-meta text-ink-3">{a.role} · can approve this quote</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
