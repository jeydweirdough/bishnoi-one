import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { accountSend, getAccount } from "@/src/platform/lib/account";
import { LinkButton } from "@/src/platform/ui/button";
import { LetterheadBlock, LetterheadFooter, loadLetterhead } from "@/src/platform/print/letterhead";
import { PrintButton } from "@/src/platform/print/print-button";
import { fmtOf, stepWho } from "@/src/one/approvals/slip-view";
import type { Slip } from "@/src/one/approvals/types";

export const metadata: Metadata = { title: "Approval slip" };

const caption = "text-[8.5pt] font-semibold tracking-wide text-neutral-600 uppercase";
const th = "py-1.5 px-2 font-semibold first:pl-0 last:pr-0";
const td = "py-1.5 px-2 first:pl-0 last:pr-0";

/**
 * An approval slip on paper (Step 4C): the official document, with the company letterhead, what was asked, each
 * step with who signed it, when, their note and their Bishnoi One signature, and what was attached.
 */
export default async function ApprovalSlipPrint({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let slip: Slip;
  try {
    slip = await accountSend<Slip>("GET", `/identity/approvals/${encodeURIComponent(id)}`);
  } catch {
    notFound();
  }
  const [head, me] = await Promise.all([loadLetterhead(), getAccount()]);
  const fmt = fmtOf(slip);
  const s = slip.summary;
  return (
    <div className="min-h-screen bg-bench print:bg-card">
      <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-rule bg-sheet px-6 py-3 print:hidden">
        <LinkButton href={`/approvals/${slip.id}`} variant="quiet">
          Back to the slip
        </LinkButton>
        <PrintButton />
      </div>
      <article className="mx-auto my-8 max-w-[210mm] bg-card px-[16mm] py-[14mm] text-[10.5pt] leading-snug text-black shadow-sm print:my-0 print:max-w-none print:p-0 print:shadow-none">
        <header className="flex items-start justify-between gap-8 border-b-2 border-black pb-4">
          <LetterheadBlock head={head} fallbackName={me.company?.name ?? ""} />
          <div className="text-right">
            <p className="text-[18pt] font-bold tracking-wide uppercase">Approval slip</p>
            <p className="font-semibold">No. {slip.number}</p>
            <p>Date: {fmt.whenLabel(slip.createdAt)}</p>
            <p className="mt-1 inline-block border-2 border-black px-2 text-[9pt] font-bold tracking-wide uppercase">{slip.statusLabel}</p>
          </div>
        </header>
        <section className="mt-4 grid grid-cols-3 gap-6">
          <div>
            <p className={caption}>Request</p>
            <p className="font-semibold">{slip.kindLabel} {slip.record.number}</p>
            {s.customer && <p>{s.customer}</p>}
          </div>
          <div>
            <p className={caption}>Requested by</p>
            <p>{slip.requestedBy.name}</p>
            {slip.requestedBy.email && <p className="text-[9pt]">{slip.requestedBy.email}</p>}
          </div>
          <div>
            <p className={caption}>Amount</p>
            <p className="font-semibold">{s.totalCentavos != null ? fmt.peso(s.totalCentavos) : "—"}</p>
            {s.warehouse && <p className="text-[9pt]">Ships from {s.warehouse}</p>}
          </div>
        </section>
        {s.lines && s.lines.length > 0 && (
          <table className="mt-5 w-full border-collapse">
            <thead>
              <tr className="border-y border-black text-left text-[9pt]">
                <th scope="col" className={`${th} w-8`}>No.</th>
                <th scope="col" className={th}>Product</th>
                <th scope="col" className={`${th} text-right`}>Quantity</th>
                <th scope="col" className={`${th} text-right`}>Amount</th>
              </tr>
            </thead>
            <tbody>
              {s.lines.map((l, i) => (
                <tr key={i} className="break-inside-avoid border-b border-neutral-300 align-top">
                  <td className={`${td} tabular-nums`}>{i + 1}</td>
                  <td className={td}>{l.name}</td>
                  <td className={`${td} text-right tabular-nums`}>{fmt.count(l.quantity)}{l.freeQuantity ? ` + ${fmt.count(l.freeQuantity)} free` : ""}{l.soldAs ? ` (${l.soldAs})` : ""}</td>
                  <td className={`${td} text-right tabular-nums`}>{l.totalCentavos ? fmt.peso(l.totalCentavos) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {s.moreLines ? <p className="mt-1 text-[9pt]">And {s.moreLines} more lines on {slip.record.number}.</p> : null}
        <section className="mt-6 break-inside-avoid">
          <p className={caption}>Approvals</p>
          <table className="mt-1 w-full border-collapse">
            <thead>
              <tr className="border-y border-black text-left text-[9pt]">
                <th scope="col" className={th}>Step</th>
                <th scope="col" className={th}>Decision</th>
                <th scope="col" className={th}>Note</th>
                <th scope="col" className={`${th} w-[45mm]`}>Signature</th>
              </tr>
            </thead>
            <tbody>
              {slip.steps.map((step) => (
                <tr key={step.id} className="break-inside-avoid border-b border-neutral-300 align-top">
                  <td className={td}>
                    <p className="font-semibold">{step.label}</p>
                    <p className="text-[9pt]">{stepWho(step)}</p>
                  </td>
                  <td className={td}>
                    {step.status === "signed" || step.status === "returned" ? (
                      <>
                        <p>{step.status === "signed" ? "Approved" : "Returned"} by {step.actedBy}{step.actedAs === "administrator" ? " (company administrator)" : ""}</p>
                        <p className="text-[9pt]">{fmt.whenLabel(step.actedAt)}</p>
                      </>
                    ) : (
                      <p>{step.status === "skipped" ? "Not needed" : "Waiting"}</p>
                    )}
                  </td>
                  <td className={td}>{step.note ?? ""}</td>
                  <td className={td}>
                    {step.signature ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={step.signature} alt={`Signature of ${step.actedBy ?? "the signer"}`} className="h-12 max-w-[42mm] object-contain" />
                    ) : (
                      <div className="mt-6 border-b border-black" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="mt-6 break-inside-avoid">
          <p className={caption}>Attached</p>
          {slip.attachments.length === 0 ? (
            <p>Nothing attached.</p>
          ) : (
            <ul className="mt-1 list-disc pl-5">
              {slip.attachments.map((a) => (
                <li key={a.id}>
                  {a.label}
                  {a.kind === "file" ? ` (file: ${a.fileName}, added by ${a.addedBy})` : ""}
                </li>
              ))}
            </ul>
          )}
        </section>
        {slip.replaces && <p className="mt-4 text-[9pt]">Sent again after {slip.replaces.number}, which was returned{slip.replaces.note ? `: ${slip.replaces.note}` : "."}</p>}
        <footer className="mt-8 border-t border-black pt-2 text-[8.5pt]">
          <LetterheadFooter head={head} />
          <p>Approval slip {slip.number} for {slip.kindLabel.toLowerCase()} {slip.record.number}, kept in Bishnoi One.</p>
        </footer>
      </article>
    </div>
  );
}
