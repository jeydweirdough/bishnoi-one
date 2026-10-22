import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { PrintButton } from "../invoices/steps";
import type { Entry } from "../ledger/types";
import { SignatureLines } from "../signature/blocks";
import type { SignedStep } from "../signature/types";

// One journal entry as a voucher, to print or save as PDF (decided 2026-10-22:
// Plans/Plan - E-signatures): Prepared by (whoever typed it) and Approved by, each
// with the signature they had when they did it.

export const metadata = { title: "Journal voucher" };

const SOURCE = { manual: "Manual journal", fund: "Marketing request", invoice: "Invoice" } as Record<string, string>;

export default async function JournalVoucherPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const { id } = await params;
  const [e, signed] = await Promise.all([
    load<Entry>(`/finance/ledger/entries/${enc(id)}`),
    load<{ steps: SignedStep[] }>(`/finance/signatures/journal_entry/${enc(id)}`),
  ]);
  const debits = e.lines.reduce((n, l) => n + l.debitCentavos, 0);
  const credits = e.lines.reduce((n, l) => n + l.creditCentavos, 0);
  const automatic = e.source !== "manual" && signed.steps.length === 0;
  return (
    <>
      <div className="print:hidden">
        <PageHeader crumbs={[{ href: `/ledger?q=${encodeURIComponent(e.number)}`, label: "Journal entries" }]} title={`Journal voucher ${e.number}`} actions={<PrintButton />}>
          Print it, or choose &quot;Save as PDF&quot; in the print window.
        </PageHeader>
      </div>
      <Sheet className="relative px-8 py-7 print:border-0 print:shadow-none">
        {e.status !== "approved" && (
          <p className="mb-4 rounded-[3px] bg-danger-tint px-3 py-2 text-sm font-semibold text-danger">
            {e.status === "waiting" ? "Waiting for approval: not in the books yet." : `Rejected by ${e.decidedBy}: ${e.rejectedReason}. Not in the books.`}
          </p>
        )}
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-ink pb-3">
          <div>
            <p className="text-meta text-ink-3 uppercase">{me.org.name}</p>
            <h2 className="text-heading">Journal voucher</h2>
          </div>
          <dl className="text-right text-sm">
            <div>
              <dt className="inline text-ink-3">No. </dt>
              <dd className="inline font-mono font-semibold">{e.number}</dd>
            </div>
            <div>
              <dt className="inline text-ink-3">Date </dt>
              <dd className="inline">{fmt.dateLabel(e.date)}</dd>
            </div>
          </dl>
        </div>
        <dl className="mt-3 grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
          <div>
            <dt className="inline text-ink-3">Particulars: </dt>
            <dd className="inline">{e.memo}</dd>
          </div>
          {e.reference && (
            <div>
              <dt className="inline text-ink-3">Reference: </dt>
              <dd className="inline">{e.reference}</dd>
            </div>
          )}
          <div>
            <dt className="inline text-ink-3">Source: </dt>
            <dd className="inline">{SOURCE[e.source] ?? e.source}</dd>
          </div>
        </dl>
        <table className="mt-4 w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
              <th className="py-2 font-semibold">Account</th>
              <th className="py-2 font-semibold">Description</th>
              <th className="w-36 py-2 text-right font-semibold">Debit</th>
              <th className="w-36 py-2 text-right font-semibold">Credit</th>
            </tr>
          </thead>
          <tbody>
            {e.lines.map((ln, i) => (
              <tr key={i} className="border-b border-rule">
                <td className={`py-1.5 ${ln.creditCentavos ? "pl-6" : ""}`}>
                  {ln.account.code} · {ln.account.name}
                </td>
                <td className="py-1.5 text-ink-2">{ln.description}</td>
                <td className="py-1.5 text-right tabular-nums">{ln.debitCentavos ? fmt.peso(ln.debitCentavos) : ""}</td>
                <td className="py-1.5 text-right tabular-nums">{ln.creditCentavos ? fmt.peso(ln.creditCentavos) : ""}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-ink font-semibold tabular-nums">
              <td className="py-2" colSpan={2}>
                Total
              </td>
              <td className="py-2 text-right">{fmt.peso(debits)}</td>
              <td className="py-2 text-right">{fmt.peso(credits)}</td>
            </tr>
          </tfoot>
        </table>
        {automatic ? (
          <p className="mt-8 text-meta text-ink-3">
            Posted automatically by {(SOURCE[e.source] ?? e.source).toLowerCase()} step, recorded by {e.postedBy}. Its signatures are on that document.
          </p>
        ) : (
          <SignatureLines
            lines={[
              { step: "prepared", label: "Prepared by" },
              { step: "approved", label: "Approved by" },
            ]}
            signed={signed.steps}
            timeZone={me.org.timezone}
          />
        )}
      </Sheet>
    </>
  );
}
