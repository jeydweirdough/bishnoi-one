import Link from "next/link";
import { PageHeader, Particulars, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { NoAccess } from "../components/admin/words";
import { CancelFunds } from "../components/funds/cancel";
import { Decide } from "../components/funds/decide";
import { FundStatusTag, FundSteps } from "../components/funds/fund-list";
import { Liquidate, Receipts, Tally } from "../components/funds/liquidation";
import type { ExpenseCategory, FundRequest } from "../components/funds/types";
import { nextFor } from "../components/funds/words";

export const metadata = { title: "Marketing request" };

/** One request: where it is, what's next and whose move it is, the money, the
 *  receipts, and its record from asking to settled. */
export default async function FundPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await getCompanyMe();
  if (!can(me, "funds.view")) return <NoAccess what="marketing requests" />;
  const { id } = await params;
  const r = await load<FundRequest & { financeProblem: string | null }>(`/funds/${enc(id)}`);
  // The categories only matter while receipts are going in.
  const categories = r.can.liquidate ? await load<{ items: ExpenseCategory[] }>("/funds/categories").then((c) => c.items).catch(() => []) : [];
  const fmt = makeFormat(me.org);
  const f = r.finance;
  const next = nextFor(r, fmt);
  const mine = r.owner.id === me.user.id;

  // The record: what happened here (asked, decided), then Finance's, in order.
  const record = [
    { at: r.createdAt, who: r.owner.name, text: `Request submitted for ${fmt.peso(r.amountCentavos)}: ${r.purpose.name}.` },
    ...(r.decision && r.status === "declined" ? [{ at: r.decision.at, who: r.decision.by?.name ?? "", text: `Declined: ${r.decision.note ?? ""}` }] : []),
    ...(r.decision && !f && r.status !== "declined" ? [{ at: r.decision.at, who: r.decision.by?.name ?? "", text: `Approved for ${fmt.peso(r.approvedCentavos ?? 0)}.` }] : []),
    ...(f?.events ?? []).map((e) => ({ at: e.at, who: e.who, text: e.text })),
  ];

  return (
    <>
      <PageHeader
        crumbs={[mine ? { href: "/funds", label: "My marketing requests" } : { href: "/funds/team", label: "Team requests" }]}
        title={
          <>
            {r.purpose.name} <span className="text-ink-3">{r.number}</span>
          </>
        }
        actions={r.can.cancel && <CancelFunds id={r.id} number={r.number} />}
      >
        <span className="flex flex-wrap items-center gap-2">
          <FundStatusTag request={r} />
          {!mine && <span>{r.owner.name}{r.team ? ` · ${r.team.name}` : ""}</span>}
        </span>
      </PageHeader>

      <div className="space-y-5">
        <Sheet className="px-5 py-4">
          <FundSteps request={r} />
          {next && <p className={`mt-3 text-sm ${r.status === "to_liquidate" || r.status === "to_return" ? "font-semibold text-due-today" : "text-ink-2"}`}>{next}</p>}
          {f?.sentBackNote && r.status === "to_liquidate" && <p className="mt-2 rounded-[6px] bg-danger-tint px-3 py-2 text-meta text-danger">Returned by Finance for correction: {f.sentBackNote}</p>}
          {r.financeProblem && <p className="mt-2 text-meta text-danger">Finance couldn&apos;t be asked just now ({r.financeProblem}); this is its last answer.</p>}
        </Sheet>

        {r.can.approve && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="approvals">Approval</SectionTitle>
            <Decide request={r} org={me.org} />
          </Sheet>
        )}

        <div className="grid gap-5 lg:grid-cols-2">
          <Sheet className="px-5 py-4">
            <SectionTitle icon="particulars">Request details</SectionTitle>
            <Particulars
              items={[
                ["Amount requested", fmt.peso(r.amountCentavos)],
                ["Amount approved", r.approvedCentavos ? fmt.peso(r.approvedCentavos) : null],
                ["Date needed", r.neededOn ? fmt.dateLabel(r.neededOn) : null],
                ["Customer", r.company ? <Link href={`/companies/${r.company.id}`} className="text-ink hover:underline">{r.company.name}</Link> : null],
                ["Subject to liquidation", r.liquidate ? "Yes" : "No"],
                ["Details", <span key="d" className="whitespace-pre-line">{r.details}</span>],
                ...(r.decision?.note ? ([[r.status === "declined" ? "Reason for declining" : "Approver's remarks", r.decision.note]] as [string, string][]) : []),
              ]}
            />
          </Sheet>

          {f?.release && (
            <Sheet className="px-5 py-4">
              <SectionTitle icon="payments">Cash advance</SectionTitle>
              <Particulars
                items={[
                  ["Released", `${fmt.peso(f.release.amountCentavos)} · ${f.release.methodLabel}${f.release.reference ? ` (${f.release.reference})` : ""}`],
                  ["Release date", fmt.whenLabel(f.release.at)],
                  ...(r.liquidate && f.release.liquidateBy ? ([["Liquidation due", fmt.dateLabel(f.release.liquidateBy)]] as [string, string][]) : []),
                ]}
              />
              {r.liquidate && (
                <div className="mt-4 border-t border-rule pt-3">
                  <Tally request={r} org={me.org} />
                </div>
              )}
            </Sheet>
          )}
        </div>

        {r.liquidate && f?.release && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="quotes">Liquidation</SectionTitle>
            <Receipts request={r} org={me.org} editable={r.can.liquidate} />
            {r.can.liquidate && (
              <div className="mt-4">
                <Liquidate request={r} categories={categories} org={me.org} today={fmt.todayKey()} />
              </div>
            )}
          </Sheet>
        )}

        <Sheet className="px-5 py-4">
          <SectionTitle icon="history">Activity log</SectionTitle>
          <ol className="space-y-2">
            {record.map((e, i) => (
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
