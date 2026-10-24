import { PageHeader, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import type { FundRequest } from "@/src/modules/finance/funds/types";
import { PrintButton } from "@/src/modules/finance/invoices/steps";
import { SignatureLines } from "@/src/modules/finance/signature/blocks";
import type { SignedStep } from "@/src/modules/finance/signature/types";

// A cash advance's liquidation as a report, to print or save as PDF (decided
// 2026-10-22: Plans/Plan - E-signatures): the receipts and what they came to, then
// Reviewed by and Settled by, each with the signature they had when they did it.

export const metadata = { title: "Liquidation report" };

export default async function LiquidationReportPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const { id } = await params;
  const [r, signed] = await Promise.all([
    load<FundRequest>(`/finance/funds/${enc(id)}`),
    load<{ steps: SignedStep[] }>(`/finance/signatures/fund_request/${enc(id)}`),
  ]);
  const t = r.tally;
  const rows: [string, number][] = [
    ["Released", r.release?.amountCentavos ?? 0],
    ["Spent (receipts)", t.spentCentavos],
    ["Accepted, company's expense", t.coveredCentavos],
    ["The person's own", t.ownCentavos],
    ["Refused", t.refusedCentavos],
  ];
  if (r.returnDueCentavos) rows.push(["Unused funds to return", r.returnDueCentavos], ["Returned", r.returnedCentavos]);
  if (r.reimburseDueCentavos) rows.push(["To reimburse", r.reimburseDueCentavos], ["Reimbursed", r.reimbursedCentavos]);
  return (
    <>
      <div className="print:hidden">
        <PageHeader crumbs={[{ href: `/finance/funds/${r.id}`, label: r.number }]} title={`Liquidation report ${r.number}`} actions={<PrintButton />}>
          Print it, or choose &quot;Save as PDF&quot; in the print window.
        </PageHeader>
      </div>
      <Sheet className="px-8 py-7 print:border-0 print:shadow-none">
        {!r.checkedAt && <p className="mb-4 rounded-[3px] bg-danger-tint px-3 py-2 text-sm font-semibold text-danger">Not reviewed yet: these figures can still change.</p>}
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-ink pb-3">
          <div>
            <p className="text-meta text-ink-3 uppercase">{me.org.name}</p>
            <h2 className="text-heading">Liquidation report</h2>
          </div>
          <dl className="text-right text-sm">
            <div>
              <dt className="inline text-ink-3">No. </dt>
              <dd className="inline font-mono font-semibold">{r.number}</dd>
            </div>
            {r.release && (
              <div>
                <dt className="inline text-ink-3">Released </dt>
                <dd className="inline">{fmt.dateLabel(r.release.at.slice(0, 10))}</dd>
              </div>
            )}
          </dl>
        </div>
        <dl className="mt-3 grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
          <div>
            <dt className="inline text-ink-3">Employee: </dt>
            <dd className="inline">
              {r.requester.name}
              {r.requester.team ? ` (${r.requester.team})` : ""}
            </dd>
          </div>
          <div>
            <dt className="inline text-ink-3">Purpose: </dt>
            <dd className="inline">{r.purpose}</dd>
          </div>
          <div>
            <dt className="inline text-ink-3">Approved by: </dt>
            <dd className="inline">{r.approval.by} (in the CRM)</dd>
          </div>
          {r.release && (
            <div>
              <dt className="inline text-ink-3">Released: </dt>
              <dd className="inline">
                {fmt.peso(r.release.amountCentavos)} via {r.release.methodLabel}
                {r.release.reference ? ` (${r.release.reference})` : ""}
              </dd>
            </div>
          )}
        </dl>
        <table className="mt-4 w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
              <th className="py-2 font-semibold">Date</th>
              <th className="py-2 font-semibold">Description</th>
              <th className="py-2 font-semibold">Category</th>
              <th className="py-2 font-semibold">Review</th>
              <th className="w-32 py-2 text-right font-semibold">Amount</th>
            </tr>
          </thead>
          <tbody>
            {r.expenses.map((x) => (
              <tr key={x.id} className="border-b border-rule align-top">
                <td className="py-1.5 whitespace-nowrap">{fmt.dateLabel(x.spentOn)}</td>
                <td className="py-1.5">
                  {x.description}
                  {!x.receipt && x.noReceiptReason && <span className="block text-meta text-ink-3">No receipt: {x.noReceiptReason}</span>}
                </td>
                <td className="py-1.5">{x.category?.name ?? ""}</td>
                <td className="py-1.5">{x.accepted === true ? "Accepted" : x.accepted === false ? `Refused${x.refusedReason ? `: ${x.refusedReason}` : ""}` : "Not reviewed"}</td>
                <td className="py-1.5 text-right tabular-nums">{fmt.peso(x.amountCentavos)}</td>
              </tr>
            ))}
            {r.expenses.length === 0 && (
              <tr>
                <td colSpan={5} className="py-3 text-center text-meta text-ink-3">
                  No receipts: all of it comes back as unused funds.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <dl className="mt-4 ml-auto max-w-sm text-sm">
          {rows.map(([label, centavos]) => (
            <div key={label} className="flex justify-between border-b border-rule py-1">
              <dt className="text-ink-2">{label}</dt>
              <dd className="tabular-nums">{fmt.peso(centavos)}</dd>
            </div>
          ))}
        </dl>
        <SignatureLines
          lines={[
            { step: "reviewed", label: "Reviewed by" },
            { step: "settled", label: "Settled by" },
          ]}
          signed={signed.steps}
          timeZone={me.org.timezone}
        />
      </Sheet>
    </>
  );
}
