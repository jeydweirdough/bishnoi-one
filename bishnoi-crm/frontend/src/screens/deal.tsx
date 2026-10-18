import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { PageHeader, Particulars, SectionTitle, Sheet, Empty } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Deal, DealLists, DealStage } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { AssociationsPanel } from "../components/crm/associations-panel";
import { EditRecord } from "../components/crm/list-controls";
import { DealClose } from "../components/deals/deal-close";
import { AppliedPromo } from "../components/catalogue/promo-tag";
import { PriorityFlag, CATEGORY_LABELS, StageTag, closeLabel } from "../components/deals/words";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    return { title: (await load<Deal>(`/deals/${enc(id)}`)).name };
  } catch {
    return { title: "Deal" };
  }
}

const APPROVAL: Record<string, string> = { none: "Ready", approved: "Approved", pending: "Waiting for approval", rejected: "Rejected" };

export default async function DealPage({ params }: { params: Params }) {
  const me = await getCompanyMe();
  if (!can(me, "deals.view")) return <NoAccess what="deals" />;
  const { id } = await params;
  const [deal, stages, lists] = await Promise.all([load<Deal>(`/deals/${enc(id)}`), load<DealStage[]>("/deal-stages"), load<DealLists>("/deal-lists")]);
  const fmt = makeFormat(me.org);
  const today = fmt.todayKey();
  const winners = deal.quotes.filter((q) => q.approvalStatus === "none" || q.approvalStatus === "approved");
  const overdue = deal.state === "open" && deal.expectedCloseOn < today;
  const wonWith = deal.quotes.find((q) => q.id === deal.wonQuoteId);

  return (
    <>
      <PageHeader
        title={
          <span className="inline-flex flex-wrap items-center gap-2.5">
            {deal.name}
            <StageTag deal={deal} />
          </span>
        }
        tools={deal.can.edit && <EditRecord href={`/deals/${deal.id}/edit`} what="deal" />}
        crumbs={[{ href: "/deals", label: "Deals" }]}
        actions={
          deal.can.quote && (
            <LinkButton href={`/companies/${deal.company.id}/quotes/new?deal=${deal.id}`} variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              New quote
            </LinkButton>
          )
        }
      >
        <Link href={`/companies/${deal.company.id}`} className="text-ink hover:underline">
          {deal.company.name}
        </Link>
        {deal.contact && <> · {deal.contact.name}</>}
      </PageHeader>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-3">
            <Sheet className="px-4 py-3">
              <p className="text-meta text-ink-3">{deal.state === "won" ? "Won" : "Expected value"}</p>
              <p className="mt-1 text-figure text-ink">{fmt.peso(deal.valueCentavos)}</p>
            </Sheet>
            <Sheet className="px-4 py-3">
              <p className="text-meta text-ink-3">Probability</p>
              <p className="mt-1 text-figure text-ink">{deal.probability}%</p>
              {deal.state === "open" && <p className="text-meta text-ink-3">{fmt.peso(deal.weightedCentavos)} weighted</p>}
            </Sheet>
            <Sheet className="px-4 py-3">
              <p className="text-meta text-ink-3">{deal.state === "open" ? "Expected to close" : "Closed"}</p>
              <p className={`mt-1 text-figure ${overdue ? "text-danger" : "text-ink"}`}>{fmt.dateLabel(deal.expectedCloseOn)}</p>
              {overdue && <p className="text-meta text-danger">Past its date: move it, or close it.</p>}
            </Sheet>
          </div>

          {(deal.can.edit || deal.can.delete) && (
            <Sheet className="px-5 py-4">
              {deal.state === "lost" && (
                <p className="mb-3 text-sm text-ink-2">
                  Lost: {deal.lostReason}
                  {deal.competitor ? `, to ${deal.competitor}` : ""}.
                </p>
              )}
              {deal.state === "won" && (
                <p className="mb-3 text-sm text-ink-2">
                  Won{wonWith ? (
                    <>
                      {" "}with quote{" "}
                      <Link href={`/quotes/${wonWith.id}`} className="text-ink hover:underline">
                        {wonWith.number}
                      </Link>
                    </>
                  ) : null}
                  .
                </p>
              )}
              <DealClose
                deal={deal}
                lists={lists}
                stages={stages}
                today={today}
                quotes={winners.map((q) => ({ id: q.id, label: `${q.number}, ${fmt.peso(q.totalCentavos)}` }))}
              />
            </Sheet>
          )}

          <Sheet className="px-5 pt-4 pb-3">
            <SectionTitle icon="products">Products</SectionTitle>
            {(deal.clidpWarnings ?? []).length > 0 && (
              <ul className="mt-2 space-y-1 rounded-sheet bg-danger-tint px-3 py-2 text-meta text-ink">
                {deal.clidpWarnings!.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            )}
            {deal.lines.length === 0 ? (
              <Empty compact icon="products" title="No products on it">Its value was typed in.{deal.can.edit ? " Edit the deal to value it by products." : ""}</Empty>
            ) : (
              <table className="mt-2 w-full text-sm">
                <thead>
                  <tr className="border-b border-rule text-left text-meta text-ink-3">
                    <th className="py-1.5 font-medium">Product</th>
                    <th className="py-1.5 text-right font-medium">Quantity</th>
                    <th className="py-1.5 text-right font-medium">Price</th>
                    <th className="py-1.5 text-right font-medium">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule">
                  {deal.lines.map((l) => (
                    <tr key={l.productId}>
                      <td className="py-2">
                        {l.productName} <span className="text-meta text-ink-3">{l.productCode}</span>
                        {/* Sold under a promo: it goes on to the deal's quote with the product. */}
                        {l.promoName && (
                          <span className="mt-1 block">
                            <AppliedPromo name={l.promoName} discountCentavos={l.promoDiscountCentavos} freeQuantity={l.freeQuantity} fmt={fmt} />
                          </span>
                        )}
                      </td>
                      <td className="py-2 text-right">
                        {fmt.count(l.quantity)} {l.unit}
                      </td>
                      <td className="py-2 text-right">{fmt.peso(l.unitPriceCentavos)}</td>
                      <td className="py-2 text-right">{fmt.peso(l.totalCentavos)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Sheet>

          <Sheet className="px-5 pt-4 pb-3">
            <SectionTitle
              icon="quotes"
              action={
                deal.can.quote && (
                  <LinkButton href={`/companies/${deal.company.id}/quotes/new?deal=${deal.id}`} size="sm" variant="quiet" icon={<Plus className="size-3.5" aria-hidden />}>
                    Add
                  </LinkButton>
                )
              }
            >
              Quotes
            </SectionTitle>
            {deal.quotes.length === 0 ? (
              <Empty compact icon="quotes" title="No quotes yet">A quote made with New quote here is linked to this deal, and can be what wins it.</Empty>
            ) : (
              <ul className="mt-1 divide-y divide-rule">
                {deal.quotes.map((q) => (
                  <li key={q.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2.5">
                    <Link href={`/quotes/${q.id}`} className="font-medium text-ink hover:underline">
                      {q.number}
                    </Link>
                    <span className="text-meta text-ink-3">
                      {APPROVAL[q.approvalStatus] ?? q.approvalStatus} · {fmt.peso(q.totalCentavos)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Sheet>
        </div>

        <div className="space-y-5">
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="particulars">Details</SectionTitle>
          <div className="mt-3">
            <Particulars
              items={[
                ["Stage", deal.stage.name],
                ["Forecast", CATEGORY_LABELS[deal.forecastCategory]],
                ["Close", closeLabel(deal, today, fmt.dateLabel)],
                ["Priority", deal.priority ? <PriorityFlag key="priority" priority={deal.priority} /> : null],
                ["Lead source", deal.leadSource],
                ["Owner", deal.owner ? (deal.owner.id === me.user.id ? "You" : deal.owner.name) : null],
                ["Added", fmt.whenLabel(deal.createdAt)],
              ]}
            />
            {deal.notes && <p className="mt-4 border-t border-rule pt-3 text-sm whitespace-pre-line text-ink-2">{deal.notes}</p>}
          </div>
        </Sheet>
        <AssociationsPanel kind="deal" id={deal.id} />
        </div>
      </div>
    </>
  );
}
