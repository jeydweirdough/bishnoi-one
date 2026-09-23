import Link from "next/link";
import { ApprovalsBulk } from "./approvals-bulk";
import { SelectAllBox, SelectBox, SelectableRow, SelectionProvider } from "@/src/platform/bulk/selection";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { load } from "@/src/platform/lib/api";
import { plural, type Format } from "@/src/platform/lib/format";
import { orgFormat } from "@/src/platform/lib/org";
import { APPROVAL_STATUSES, LETTER_STATUSES, PAYMENT_STATUSES, approvalReason } from "@/src/platform/lib/labels";
import { departmentModule } from "@/src/platform/lib/module";
import type { FinanceTask, Quote } from "@/src/platform/lib/types";

const TASKS: Record<FinanceTask, { title: string; intro: string; empty: string; done: string }> = {
  approvals: {
    title: "Approvals",
    intro: "Quotes at a price that needs approval, and extra discounts over a division's limit. Oldest first.",
    empty: "Nothing waiting for approval.",
    done: "Recently approved and rejected",
  },
  letters: {
    title: "Guarantee letters",
    intro: "Check each letter against its file: the number, the date, the amount and who it's for.",
    empty: "No letters waiting to be checked.",
    done: "Recently checked",
  },
  payments: {
    title: "Letter payments",
    intro: "Verified letters the issuer hasn't paid in full yet. Record each payment as it comes in.",
    empty: "No letters waiting on payment.",
    done: "Paid in full",
  },
};

function Detail({ fmt, task, quote }: { fmt: Format; task: FinanceTask; quote: Quote }) {
  if (task === "approvals") {
    return (
      <>
        {quote.approval.status === "pending" ? (
          quote.approval.reasons.map((r) => (
            <span key={r} className="block">
              {approvalReason(r, quote)}
            </span>
          ))
        ) : (
          <span className="block">
            {APPROVAL_STATUSES[quote.approval.status]} by {quote.approval.by?.name} · {fmt.whenLabel(quote.approval.at)}
          </span>
        )}
      </>
    );
  }
  const letter = quote.letter;
  if (!letter) return null;
  if (task === "letters") {
    return (
      <span className="block">
        {quote.payerName} {letter.number} · {fmt.dateLabel(letter.issuedOn)} · covers {fmt.peso(letter.amountCentavos)}
        {letter.status !== "pending" && ` · ${LETTER_STATUSES[letter.status]} by ${letter.by?.name}`}
      </span>
    );
  }
  return (
    <span className="block">
      {quote.payerName} {letter.number} · {PAYMENT_STATUSES[quote.payment.status]}: {fmt.peso(quote.payment.paidCentavos)} of{" "}
      {fmt.peso(letter.amountCentavos)}
    </span>
  );
}

// Everything on a waiting list is to do, so nothing is flagged; how long it has waited is what differs.
function ageDays(fmt: Format, createdAt: string): number {
  return Math.max(0, Math.round((Date.parse(fmt.todayKey()) - Date.parse(createdAt.slice(0, 10))) / 86_400_000));
}

/** One of Finance's lists: what's waiting, or (state=done) what was recently finished. */
export async function FinanceTaskList({ module, task, state }: { module: string; task: FinanceTask; state: "open" | "done" }) {
  await departmentModule(module, "finance"); // 404 anywhere but Finance
  const fmt = await orgFormat();
  const { items } = await load<{ items: Quote[] }>(`/finance/quotes?task=${task}&state=${state}`);
  const copy = TASKS[task];
  // Approvals can be decided several at once. Letters and payments can't: each needs its own look.
  const decidable = task === "approvals" && state === "open" ? items.filter((q) => q.can.approve) : [];
  const bulk = decidable.length > 0;
  return (
    <SelectionProvider key={`${task}-${state}`} items={decidable.map((q) => ({ id: q.id, name: `${q.number} · ${q.customerName ?? ""}` }))}>
      <PageHeader title={copy.title}>
        {copy.intro}
      </PageHeader>
      <div className="mb-3">
        <ToggleLinks
          current={state}
          options={[
            { value: "open", label: "Waiting", href: `/m/${module}/${task}` },
            { value: "done", label: copy.done, href: `/m/${module}/${task}?state=done` },
          ]}
        />
      </div>
      <Sheet>
        {bulk && (
          <div className="border-b border-rule px-5">
            <SelectAllBox>
              <span className="text-meta font-semibold text-ink-2">Select all {decidable.length}</span>
            </SelectAllBox>
          </div>
        )}
        {items.length === 0 ? (
          <Empty title={state === "open" ? copy.empty : "Nothing here yet"} />
        ) : (
          <ul className="divide-y divide-rule">
            {items.map((q) => (
              <SelectableRow key={q.id} id={q.id} as="li" className="flex items-start">
                {bulk && (
                  <span className="w-9 shrink-0 pt-4 pl-5">
                    {q.can.approve && <SelectBox id={q.id} label={`${q.number}, ${q.customerName ?? ""}`} />}
                  </span>
                )}
                <Link
                  // ?from tells the quote page it is being read by Finance, and
                  // which of its lists to go back to.
                  href={`/quotes/${q.id}?from=${task}`}
                  className={`flex min-w-0 flex-1 flex-wrap items-start justify-between gap-x-6 gap-y-1 py-3.5 pr-5 hover:bg-bench/40 ${bulk ? "pl-3" : "pl-5"}`}
                >
                  <span className="min-w-0">
                    <span className="font-semibold text-hema">
                      {q.number} · {q.customerName}
                    </span>
                    <span className="block text-meta text-ink-3">
                      {q.divisionName} · {q.teamName} · {q.priceTypeName} · by {q.createdBy.name}, {fmt.whenLabel(q.createdAt)}
                    </span>
                    <span className="mt-0.5 block text-meta text-ink-2">
                      <Detail fmt={fmt} task={task} quote={q} />
                    </span>
                  </span>
                  <span className="text-right">
                    <span className="block font-semibold tabular-nums">{fmt.peso(q.totalCentavos)}</span>
                    {state === "open" && (
                      <span className="block text-meta text-ink-3">{plural(ageDays(fmt, q.createdAt), "day")} waiting</span>
                    )}
                  </span>
                </Link>
              </SelectableRow>
            ))}
          </ul>
        )}
      </Sheet>
      {bulk && <ApprovalsBulk />}
    </SelectionProvider>
  );
}
