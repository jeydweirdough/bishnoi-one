import { FileText } from "lucide-react";
import { LinkButton } from "@/src/modules/finance/platform/ui/button";
import { PageHeader, Particulars, SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { CheckLiquidation, RecordMoney, Release } from "@/src/modules/finance/funds/steps";
import type { ExpenseCategory, FundRequest } from "@/src/modules/finance/funds/types";

export const metadata = { title: "Marketing request" };

/** The queue each status sits in, for the breadcrumb. */
const QUEUE: Record<string, { href: string; label: string }> = {
  to_release: { href: "/finance/funds", label: "For release" },
  to_liquidate: { href: "/finance/funds/outstanding", label: "Outstanding" },
  to_check: { href: "/finance/funds/review", label: "For review" },
  to_return: { href: "/finance/funds/settlement", label: "For settlement" },
  to_reimburse: { href: "/finance/funds/settlement", label: "For settlement" },
  closed: { href: "/finance/funds/history", label: "History" },
  cancelled: { href: "/finance/funds/history", label: "History" },
};

/** One request: the action Finance takes at this step, the request and its
 *  cash advance, the liquidation, the journal entries, and the activity log. */
export default async function FundPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await getCompanyMe();
  const { id } = await params;
  const r = await load<FundRequest>(`/finance/funds/${enc(id)}`);
  const categories = r.status === "to_check" ? (await load<{ items: ExpenseCategory[] }>("/finance/funds/categories")).items.filter((c) => c.isActive) : [];
  const fmt = makeFormat(me.org);
  const t = r.tally;
  // Each step only for a role that may take it; the API checks the same.
  const may = (p: string) => me.permissions?.includes(p) ?? false;

  return (
    <>
      <PageHeader
        crumbs={[QUEUE[r.status]]}
        actions={
          // The signed report, once the liquidation is reviewed (decided 2026-10-22: e-signatures).
          r.checkedAt ? (
            <LinkButton href={`/finance/funds/${r.id}/report`} icon={<FileText className="size-4" aria-hidden />}>
              Liquidation report
            </LinkButton>
          ) : undefined
        }
        title={
          <>
            {r.requester.name} · {r.purpose} <span className="text-ink-3">{r.number}</span>
          </>
        }
      >
        <span className={`rounded-full px-2 py-0.5 text-meta font-medium ${r.overdue ? "bg-danger-tint text-danger" : "bg-hema-tint text-hema"}`}>
          {r.overdue ? "Liquidation overdue" : r.statusLabel}
        </span>
      </PageHeader>

      <div className="space-y-5">
        {r.status === "to_release" && may("funds.release") && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="payments">Release cash advance</SectionTitle>
            {r.holds?.release ? <p className="text-sm text-ink-2">{r.holds.release}</p> : <Release request={r} org={me.org} today={fmt.todayKey()} />}
          </Sheet>
        )}
        {r.status === "to_check" && may("funds.check") && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="approvals">Liquidation review</SectionTitle>
            {r.holds?.check ? <p className="text-sm text-ink-2">{r.holds.check}</p> : <CheckLiquidation request={r} categories={categories} org={me.org} />}
          </Sheet>
        )}
        {(r.status === "to_return" || r.status === "to_reimburse") && may("funds.settle") && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="payments">{r.status === "to_return" ? "Record refund" : "Record reimbursement"}</SectionTitle>
            <RecordMoney request={r} org={me.org} kind={r.status === "to_return" ? "returned" : "reimbursed"} />
          </Sheet>
        )}

        <div className="grid gap-5 lg:grid-cols-2">
          <Sheet className="px-5 py-4">
            <SectionTitle icon="particulars">Request details</SectionTitle>
            <Particulars
              items={[
                ["Requested by", `${r.requester.name}${r.requester.team ? ` · ${r.requester.team}` : ""} (${r.requester.email})`],
                ["Amount requested", fmt.peso(r.requestedCentavos)],
                ["Amount approved", `${fmt.peso(r.approvedCentavos)} by ${r.approval.by}, ${fmt.whenLabel(r.approval.at)}`],
                ["Approver's remarks", r.approval.note],
                ["Date needed", r.neededOn ? fmt.dateLabel(r.neededOn) : null],
                ["Customer", r.customerName],
                ["Subject to liquidation", r.liquidate ? "Yes" : "No: settled upon release"],
                ["Details", r.details ? <span key="d" className="whitespace-pre-line">{r.details}</span> : null],
                ["Source", r.sourceApp === "crm" ? "Bishnoi One CRM" : r.sourceApp],
              ]}
            />
          </Sheet>
          {r.release && (
            <Sheet className="px-5 py-4">
              <SectionTitle icon="payments">Cash advance</SectionTitle>
              <Particulars
                items={[
                  ["Released", `${fmt.peso(r.release.amountCentavos)} · ${r.release.methodLabel}${r.release.reference ? ` (${r.release.reference})` : ""}`],
                  ["Release date", fmt.whenLabel(r.release.at)],
                  ["Liquidation due", r.liquidate && r.release.liquidateBy ? fmt.dateLabel(r.release.liquidateBy) : null],
                ]}
              />
              {r.liquidate && (
                <dl className="mt-4 space-y-1 border-t border-rule pt-3 text-sm">
                  {(
                    [
                      ["Total expenses", t.spentCentavos],
                      ["Charged to company (reimbursable)", t.coveredCentavos],
                      ["Personal (non-reimbursable)", t.ownCentavos],
                      ["Rejected", t.refusedCentavos],
                    ] as [string, number][]
                  )
                    .filter(([, v], i) => i < 2 || v > 0)
                    .map(([label, v]) => (
                      <div key={label} className="flex justify-between gap-4">
                        <dt className="text-ink-2">{label}</dt>
                        <dd className="tabular-nums">{fmt.peso(v)}</dd>
                      </div>
                    ))}
                  <div className="flex justify-between gap-4 border-t border-rule pt-1.5 font-semibold">
                    <dt>
                      {t.balanceCentavos === 0
                        ? "Fully liquidated"
                        : r.status === "closed"
                          ? t.balanceCentavos > 0
                            ? "Refund received"
                            : "Reimbursement paid"
                          : t.balanceCentavos > 0
                            ? "Refund due from employee"
                            : "Reimbursement due to employee"}
                    </dt>
                    <dd className="tabular-nums">{fmt.peso(Math.abs(t.balanceCentavos))}</dd>
                  </div>
                  {r.returnedCentavos > 0 && <p className="text-meta text-ink-2">Refund received: {fmt.peso(r.returnedCentavos)} of {fmt.peso(r.returnDueCentavos)}</p>}
                  {r.reimbursedCentavos > 0 && <p className="text-meta text-ink-2">Reimbursement paid: {fmt.peso(r.reimbursedCentavos)} of {fmt.peso(r.reimburseDueCentavos)}</p>}
                </dl>
              )}
            </Sheet>
          )}
        </div>

        {r.liquidate && r.status !== "to_check" && r.expenses.length > 0 && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="quotes">Liquidation</SectionTitle>
            <ul className="divide-y divide-rule">
              {r.expenses.map((e) => (
                <li key={e.id} className="flex flex-wrap items-start gap-x-4 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{e.description}</p>
                    <p className="text-meta text-ink-3">
                      {fmt.dateLabel(e.spentOn)} · {e.category?.name ?? "Unclassified"}
                    </p>
                    {e.receipt ? (
                      <a href={`/finance/funds/${r.id}/receipts/${e.id}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-meta text-hema hover:underline">
                        <FileText className="size-3.5" aria-hidden />
                        {e.receipt.name}
                      </a>
                    ) : (
                      <p className="text-meta text-ink-2">No official receipt: {e.noReceiptReason}</p>
                    )}
                    {e.accepted === false && <p className="text-meta text-danger">Rejected: {e.refusedReason}</p>}
                  </div>
                  <p className={`text-sm tabular-nums ${e.covered ? "" : "text-ink-3 line-through"}`}>{fmt.peso(e.amountCentavos)}</p>
                </li>
              ))}
            </ul>
          </Sheet>
        )}

        {r.entries.length > 0 && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="lists">Journal entries</SectionTitle>
            <ul className="divide-y divide-rule">
              {r.entries.map((e) => (
                <li key={e.id} className="flex flex-wrap items-baseline gap-x-3 py-2 text-sm">
                  {/* Found by its number, so it's there however far back it is (the journal shows the newest 200). */}
                  <a href={`/finance/ledger?q=${encodeURIComponent(e.number)}#${e.number}`} className="font-mono text-meta font-semibold text-hema hover:underline">
                    {e.number}
                  </a>
                  <span className="text-meta text-ink-3">{fmt.dateLabel(e.date)}</span>
                  <span className="min-w-0 flex-1">{e.memo}</span>
                  <span className="tabular-nums">{fmt.peso(e.totalCentavos)}</span>
                </li>
              ))}
            </ul>
          </Sheet>
        )}

        <Sheet className="px-5 py-4">
          <SectionTitle icon="history">Activity log</SectionTitle>
          <ol className="space-y-2">
            {r.events.map((e, i) => (
              <li key={i} className="grid grid-cols-[8.5rem_minmax(0,1fr)] gap-3 text-sm">
                <span className="text-meta text-ink-3">{fmt.whenLabel(e.at)}</span>
                <span>
                  {e.text} <span className="text-ink-3">· {e.who}</span>
                </span>
              </li>
            ))}
          </ol>
        </Sheet>
      </div>
    </>
  );
}
