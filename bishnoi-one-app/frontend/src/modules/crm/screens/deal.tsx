import { Banknote, Building2, CalendarCheck, CalendarClock, CircleAlert, CircleCheck, CircleX, Clock, FileText, Flag, Hourglass, Package, Percent, Plus, Scale, User, UserPlus } from "lucide-react";
import { NextSteps, type NextStep } from "@/src/platform/ui/next-steps";
import { Amount } from "@/src/platform/ui/amount";
import { Tip } from "@/src/platform/ui/tip";
import { shorten } from "@/src/platform/lib/short-amount";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { PageHeader, Particulars, SectionTitle, Sheet, Empty } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Deal, DealLists, DealStage } from "@/src/platform/lib/types";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { AssociationsPanel } from "@/src/modules/crm/components/crm/associations-panel";
import { EditRecord } from "@/src/modules/crm/components/crm/list-controls";
import { DealClose } from "@/src/modules/crm/components/deals/deal-close";
import { AppliedPromo } from "@/src/modules/crm/components/catalogue/promo-tag";
import { PriorityFlag, CATEGORY_LABELS, StageTag, closeLabel } from "@/src/modules/crm/components/deals/words";
import { StageTrack } from "@/src/modules/crm/components/deals/stage-track";

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
// A quote's approval as an icon in its colour; the word is in its tip.
const APPROVAL_MARK: Record<string, { icon: typeof CircleCheck; tone: string }> = {
  none: { icon: CircleCheck, tone: "text-sage-deep" },
  approved: { icon: CircleCheck, tone: "text-sage-deep" },
  pending: { icon: Clock, tone: "text-due-today" },
  rejected: { icon: CircleX, tone: "text-danger" },
};

/** Whole days from one YYYY-MM-DD to another (negative when it's gone by). */
const daysBetween = (from: string, to: string) => Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000);
const short = (text: string) => shorten(text) ?? text;

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
  const left = daysBetween(today, deal.expectedCloseOn);
  // What the deal still needs, most pressing first; each opens where it's filled in.
  const edit = `/crm/deals/${deal.id}/edit`;
  const todo: NextStep[] =
    deal.state !== "open"
      ? []
      : [
          ...(overdue && deal.can.edit ? [{ label: "Move the close date", href: edit, icon: CalendarClock, urgent: true }] : []),
          ...(deal.lines.length === 0 && deal.can.edit ? [{ label: "Add products", href: edit, icon: Package }] : []),
          ...(deal.quotes.length === 0 && deal.can.quote ? [{ label: "Make a quote", href: `/crm/customers/${deal.company.id}/quotes/new?deal=${deal.id}`, icon: FileText }] : []),
          ...(!deal.contact && deal.can.edit ? [{ label: "Add a contact", href: edit, icon: UserPlus }] : []),
          ...(!deal.priority && deal.can.edit ? [{ label: "Set the priority", href: edit, icon: Flag }] : []),
        ];

  return (
    <>
      <PageHeader
        title={
          <span className="inline-flex flex-wrap items-center gap-2.5">
            {deal.name}
            <StageTag deal={deal} />
          </span>
        }
        tools={deal.can.edit && <EditRecord href={`/crm/deals/${deal.id}/edit`} what="deal" />}
        crumbs={[{ href: "/crm/deals", label: "Deals" }]}
        actions={
          deal.can.quote && (
            <LinkButton href={`/crm/customers/${deal.company.id}/quotes/new?deal=${deal.id}`} variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              New quote
            </LinkButton>
          )
        }
      >
        <span className="inline-flex flex-wrap items-center gap-x-4 gap-y-1">
          <Link href={`/crm/customers/${deal.company.id}`} className="inline-flex items-center gap-1.5 text-ink hover:underline">
            <Building2 className="size-4 text-ink-3" aria-hidden />
            {deal.company.name}
          </Link>
          {deal.contact && (
            <span className="inline-flex items-center gap-1.5">
              <User className="size-4 text-ink-3" aria-hidden />
              {deal.contact.name}
            </span>
          )}
        </span>
        <StageTrack dealId={deal.id} current={deal.stage.code} state={deal.state} stages={stages} canMove={deal.can.edit} />
      </PageHeader>

      <NextSteps steps={todo} />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-3">
            <Sheet className="px-4 py-3">
              <p className="flex items-center gap-1.5 text-meta text-ink-3">
                <Banknote className="size-3.5" aria-hidden />
                {deal.state === "won" ? "Won" : "Expected value"}
              </p>
              <p className="mt-1 text-figure text-ink">
                <Amount text={fmt.peso(deal.valueCentavos)} />
              </p>
            </Sheet>
            <Sheet className="px-4 py-3">
              <p className="flex items-center gap-1.5 text-meta text-ink-3">
                <Percent className="size-3.5" aria-hidden />
                Probability
              </p>
              <p className="mt-1 text-figure text-ink">{deal.probability}%</p>
              {deal.state === "open" && (
                <Tip tip={`Weighted by probability: ${fmt.peso(deal.weightedCentavos)}`} className="mt-0.5 inline-flex items-center gap-1 text-meta text-ink-3 tabular-nums">
                  <Scale className="size-3" aria-hidden />
                  {short(fmt.peso(deal.weightedCentavos))}
                </Tip>
              )}
            </Sheet>
            <Sheet className="px-4 py-3">
              <p className="flex items-center gap-1.5 text-meta text-ink-3">
                <CalendarCheck className="size-3.5" aria-hidden />
                {deal.state === "open" ? "Expected to close" : "Closed"}
              </p>
              <p className={`mt-1 flex items-center gap-1.5 text-figure ${overdue ? "text-danger" : "text-ink"}`}>
                {overdue && <CircleAlert className="size-5" aria-hidden />}
                {fmt.dateLabel(deal.expectedCloseOn)}
              </p>
              {deal.state === "open" && (
                <Tip
                  tip={overdue ? `Overdue by ${fmt.plural(-left, "day")}: move the date, or close the deal` : left === 0 ? "Closes today" : `Closes in ${fmt.plural(left, "day")}`}
                  className={`mt-0.5 inline-flex items-center gap-1 rounded-md text-meta tabular-nums ${
                    overdue ? "bg-danger-tint px-1.5 font-medium text-danger" : left <= 7 ? "bg-[#fdf3e1] px-1.5 font-medium text-due-today" : "text-ink-3"
                  }`}
                >
                  <Hourglass className="size-3" aria-hidden />
                  {left === 0 ? "Today" : `${Math.abs(left)}d`}
                </Tip>
              )}
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
                      <Link href={`/crm/quotes/${wonWith.id}`} className="text-ink hover:underline">
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
                quotes={winners.map((q) => ({ id: q.id, label: `${q.number} · ${short(fmt.peso(q.totalCentavos))}` }))}
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
                      <td className="py-2 text-right tabular-nums">
                        <Amount text={fmt.peso(l.unitPriceCentavos)} />
                      </td>
                      <td className="py-2 text-right font-medium text-ink tabular-nums">
                        <Amount text={fmt.peso(l.totalCentavos)} />
                      </td>
                    </tr>
                  ))}
                </tbody>
                {deal.lines.length > 1 && (
                  <tfoot>
                    <tr className="border-t border-rule">
                      <td colSpan={3} className="py-2 text-right text-meta text-ink-3">Total</td>
                      <td className="py-2 text-right font-semibold text-ink tabular-nums">
                        <Amount text={fmt.peso(deal.lines.reduce((t, l) => t + l.totalCentavos, 0))} />
                      </td>
                    </tr>
                  </tfoot>
                )}
              </table>
            )}
          </Sheet>

          <Sheet className="px-5 pt-4 pb-3">
            <SectionTitle
              icon="quotes"
              action={
                deal.can.quote && (
                  <LinkButton href={`/crm/customers/${deal.company.id}/quotes/new?deal=${deal.id}`} size="sm" variant="quiet" icon={<Plus className="size-3.5" aria-hidden />}>
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
                    <Link href={`/crm/quotes/${q.id}`} className="font-medium text-ink hover:underline">
                      {q.number}
                    </Link>
                    <span className="inline-flex items-center gap-3 text-sm">
                      {(() => {
                        const mark = APPROVAL_MARK[q.approvalStatus] ?? APPROVAL_MARK.none;
                        return (
                          <Tip tip={APPROVAL[q.approvalStatus] ?? q.approvalStatus} className={`inline-flex ${mark.tone}`}>
                            <mark.icon className="size-4" aria-hidden />
                          </Tip>
                        );
                      })()}
                      <Amount className="font-medium text-ink tabular-nums" text={fmt.peso(q.totalCentavos)} />
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
