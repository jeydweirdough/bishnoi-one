import type { ReactNode } from "react";
import Link from "next/link";
import { Check, Clock, CornerUpLeft, FileText, Link2, Minus } from "lucide-react";
import { makeFormat } from "@/src/platform/lib/format";
import { Sheet } from "@/src/platform/ui/sheet";
import type { Slip, SlipBrief, SlipStep } from "./types";

// An approval slip on screen (Step 4C): what is asked, each step with who signed or returned it, when and with
// what note (and their signature), and what proves it. Drawn the same on the slip's page and on the record's.

export function fmtOf(slip: Pick<SlipBrief, "summary">) {
  return makeFormat({ currency: slip.summary.currency || "PHP", locale: "en-PH", timezone: "Asia/Manila" });
}

export const SLIP_TONE: Record<SlipBrief["status"], string> = {
  pending: "border-due-today text-due-today",
  approved: "border-hema text-hema",
  returned: "border-danger text-danger",
  cancelled: "border-ink-3 text-ink-3",
};

export function SlipStamp({ slip }: { slip: Pick<SlipBrief, "status" | "statusLabel" | "waitingOn"> }) {
  return (
    <span className={`inline-block rounded-lg border px-1.5 text-meta font-semibold ${SLIP_TONE[slip.status]}`}>
      {slip.status === "pending" && slip.waitingOn ? `Waiting on ${slip.waitingOn}` : slip.statusLabel}
    </span>
  );
}

const STEP_ICON = { signed: Check, returned: CornerUpLeft, waiting: Clock, skipped: Minus } as const;

/** Who a step waits for: a named person from the org chart, or anyone holding the app's approve permission. */
export function stepWho(step: SlipStep): string {
  if (step.approver?.name) return step.approver.name;
  if (step.group) return step.group.app === "inventory" && step.group.permission === "sales.approve" ? "Anyone who approves sales orders" : "Anyone who may approve it";
  return "Approver";
}

export function SlipSteps({ slip }: { slip: Slip }) {
  const fmt = fmtOf(slip);
  return (
    <ol className="space-y-3">
      <li className="flex gap-3">
        <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-mint-2 text-sage-deep" aria-hidden>
          <FileText className="size-3.5" />
        </span>
        <div className="min-w-0 text-sm">
          <p className="font-medium text-ink">Requested by {slip.requestedBy.name}</p>
          <p className="text-meta text-ink-3">{fmt.whenLabel(slip.createdAt)}</p>
        </div>
      </li>
      {slip.steps.map((s) => {
        const Icon = STEP_ICON[s.status];
        const tone =
          s.status === "signed" ? "bg-primary text-primary-foreground" : s.status === "returned" ? "bg-danger text-white" : s.current ? "bg-promo-tint text-ink" : "bg-bench text-ink-3";
        return (
          <li key={s.id} className="flex gap-3" aria-current={s.current ? "step" : undefined}>
            <span className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full ${tone}`} aria-hidden>
              <Icon className="size-3.5" />
            </span>
            <div className="min-w-0 flex-1 text-sm">
              <p className="text-ink">
                <span className="font-medium">{s.label}</span> <span className="text-ink-2">· {stepWho(s)}</span>
              </p>
              {s.status === "signed" || s.status === "returned" ? (
                <p className="text-meta text-ink-3">
                  {s.status === "signed" ? "Signed" : "Returned"} by {s.actedBy}
                  {s.actedAs === "administrator" ? " as company administrator" : ""}, {fmt.whenLabel(s.actedAt)}
                </p>
              ) : (
                <p className="text-meta text-ink-3">{s.current ? "Waiting" : s.status === "skipped" ? "Not needed" : "Next"}</p>
              )}
              {s.note && <p className="mt-1 rounded-lg bg-bench px-2 py-1 text-sm text-ink-2">{s.note}</p>}
              {s.signature && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={s.signature} alt={`Signature of ${s.actedBy ?? "the signer"}`} className="mt-1 h-10 max-w-[12rem] object-contain" />
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function SlipAttachments({ slip }: { slip: Slip }) {
  if (slip.attachments.length === 0) return <p className="text-sm text-ink-3">Nothing attached.</p>;
  return (
    <ul className="space-y-1.5">
      {slip.attachments.map((a) => {
        const Icon = a.kind === "file" ? FileText : Link2;
        const label = (
          <>
            <Icon className="size-4 shrink-0 text-ink-3" aria-hidden />
            <span className="truncate">{a.label}</span>
          </>
        );
        const look = "inline-flex max-w-full items-center gap-2 text-hema hover:underline";
        return (
          <li key={a.id} className="text-sm">
            {a.kind === "file" ? (
              <a href={`/approvals/${slip.id}/files/${a.id}`} target="_blank" rel="noreferrer" className={look}>{label}</a>
            ) : a.url ? (
              <Link href={a.url} className={look}>{label}</Link>
            ) : (
              <span className="inline-flex max-w-full items-center gap-2 text-ink">{label}</span>
            )}
            {a.kind === "file" && <span className="ml-6 block text-meta text-ink-3">Added by {a.addedBy}</span>}
          </li>
        );
      })}
    </ul>
  );
}

/** What is asked: the customer, the amount and the lines, as the app sent them. */
export function SlipSummary({ slip }: { slip: SlipBrief }) {
  const fmt = fmtOf(slip);
  const s = slip.summary;
  return (
    <div className="space-y-2 text-sm">
      <div className="flex flex-wrap gap-x-8 gap-y-1">
        {s.customer && (
          <p>
            <span className="text-ink-3">Customer </span>
            <span className="font-medium text-ink">{s.customer}</span>
          </p>
        )}
        {s.totalCentavos != null && (
          <p>
            <span className="text-ink-3">Total </span>
            <span className="font-semibold text-ink tabular-nums">{fmt.peso(s.totalCentavos)}</span>
          </p>
        )}
        {s.warehouse && (
          <p>
            <span className="text-ink-3">Ships from </span>
            {s.warehouse}
          </p>
        )}
        {s.salesperson && (
          <p>
            <span className="text-ink-3">Salesperson </span>
            {s.salesperson}
          </p>
        )}
      </div>
      {s.lines && s.lines.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-meta text-ink-3">
              <th scope="col" className="py-1 font-medium">Product</th>
              <th scope="col" className="py-1 text-right font-medium">Quantity</th>
              <th scope="col" className="py-1 text-right font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {s.lines.map((l, i) => (
              <tr key={i} className="border-b border-rule last:border-0">
                <td className="py-1">{l.name}</td>
                <td className="py-1 text-right tabular-nums">
                  {fmt.count(l.quantity)}
                  {l.freeQuantity ? ` + ${fmt.count(l.freeQuantity)} free` : ""}
                  {l.soldAs && <span className="block text-meta text-ink-3">{l.soldAs}</span>}
                </td>
                <td className="py-1 text-right tabular-nums">{l.totalCentavos ? fmt.peso(l.totalCentavos) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {s.moreLines ? <p className="text-meta text-ink-3">And {s.moreLines} more lines on the record.</p> : null}
    </div>
  );
}

/** The slip as a card on its record's page: its number and where it is, the steps, what's attached, and the actions. */
export function SlipCard({ slip, actions }: { slip: Slip; actions?: ReactNode }) {
  return (
    <Sheet className="mb-5 px-5 py-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm">
          <span className="text-caps text-ink-3 uppercase">Approval slip </span>
          <Link href={`/approvals/${slip.id}`} className="font-semibold text-hema hover:underline">
            {slip.number}
          </Link>{" "}
          <SlipStamp slip={slip} />
        </p>
        <Link href={`/approvals/${slip.id}/print`} prefetch={false} className="text-sm text-ink-2 hover:text-ink hover:underline">
          Print
        </Link>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <SlipSteps slip={slip} />
        <div>
          <p className="mb-1.5 text-caps text-ink-3 uppercase">Attached</p>
          <SlipAttachments slip={slip} />
        </div>
      </div>
      {actions}
    </Sheet>
  );
}
