import Link from "next/link";
import { Empty, PageHeader, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat, type Format } from "@/src/modules/finance/platform/lib/format";
import { CategoriesEditor } from "@/src/modules/finance/funds/categories-editor";
import type { Chart } from "@/src/modules/finance/ledger/types";
import type { ExpenseCategory, FundRequest } from "@/src/modules/finance/funds/types";

// Marketing requests, by what Finance does next: release, review, settle. Refunds
// and reimbursements are one settlement queue; settled and cancelled requests
// are one history. Each is a sub-page of Marketing requests in the sidebar.

export type FundTask = "to_release" | "to_check" | "to_settle" | "to_liquidate" | "history";

const TASKS: Record<FundTask, { title: string; intro: string; empty: string }> = {
  to_release: {
    title: "For release",
    intro: "Requests approved by the requester's Team Lead in the CRM, oldest first. Release the cash advance, or decline the release with a reason.",
    empty: "No requests for release.",
  },
  to_check: {
    title: "For review",
    intro: "Submitted liquidations, oldest first. Accept or reject each expense, then complete the review.",
    empty: "No liquidations for review.",
  },
  to_settle: {
    title: "For settlement",
    intro: "Reviewed liquidations with a balance: a refund due from the employee, or a reimbursement due to them.",
    empty: "No liquidations for settlement.",
  },
  to_liquidate: {
    title: "Outstanding",
    intro: "Cash advances released and not yet liquidated. Overdue items first.",
    empty: "No outstanding cash advances.",
  },
  history: {
    title: "History",
    intro: "Settled and cancelled requests, newest first.",
    empty: "No settled or cancelled requests yet.",
  },
};

/** The amount that matters at this step, and what it is. */
function Amount({ r, fmt }: { r: FundRequest; fmt: Format }) {
  const [label, value] =
    r.status === "to_return"
      ? ["refund due", r.returnDueCentavos - r.returnedCentavos]
      : r.status === "to_reimburse"
        ? ["reimbursement due", r.reimburseDueCentavos - r.reimbursedCentavos]
        : r.status === "to_check"
          ? ["total expenses", r.tally.spentCentavos]
          : r.release
            ? ["cash advance", r.release.amountCentavos]
            : ["approved", r.approvedCentavos];
  return (
    <p className="text-right">
      <span className="block text-sm font-semibold tabular-nums">{fmt.peso(value)}</span>
      <span className="block text-meta text-ink-3">{label}</span>
    </p>
  );
}

export default async function FundsPage({ task }: { task: FundTask }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const t = TASKS[task];
  const list = await load<{ items: FundRequest[] }>(`/finance/funds?task=${task}`);
  const items = task === "to_liquidate" ? [...list.items].sort((a, b) => Number(b.overdue) - Number(a.overdue)) : list.items;
  // Where more than one status shares a page, each row says which.
  const mixed = task === "to_settle" || task === "history";
  return (
    <>
      <PageHeader title={t.title}>{t.intro}</PageHeader>
      <Sheet>
        {items.length === 0 ? (
          <Empty title={t.empty} icon="payments">
            Requests arrive from the CRM once a Team Lead approves them.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {items.map((r) => (
              <li key={r.id}>
                <Link href={`/finance/funds/${r.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3 hover:bg-bench/60">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold">
                      {r.requester.name}
                      <span className="font-normal text-ink-2">
                        {" "}
                        · {r.purpose}
                        {r.customerName && ` · ${r.customerName}`}
                      </span>
                    </p>
                    <p className="truncate text-meta text-ink-3">
                      {r.number}
                      {r.requester.team && ` · ${r.requester.team}`} · approved by {r.approval.by}, {fmt.whenLabel(r.approval.at)}
                      {r.neededOn && task === "to_release" && ` · needed by ${fmt.dateLabel(r.neededOn)}`}
                      {r.release?.liquidateBy && task === "to_liquidate" && ` · liquidation due ${fmt.dateLabel(r.release.liquidateBy)}`}
                    </p>
                  </div>
                  {r.overdue && <span className="rounded-full bg-danger-tint px-2 py-0.5 text-meta font-medium text-danger">Overdue</span>}
                  {!r.liquidate && task === "to_release" && <span className="rounded-full bg-bench px-2 py-0.5 text-meta text-ink-2">Not subject to liquidation</span>}
                  {mixed && <span className="rounded-full bg-bench px-2 py-0.5 text-meta text-ink-2">{r.statusLabel}</span>}
                  <Amount r={r} fmt={fmt} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}

/** Expense categories and sub-categories, each category posting to an expense account. */
export async function CategoriesPage() {
  const [categories, chart] = await Promise.all([
    load<{ items: ExpenseCategory[]; canEdit: boolean }>("/finance/funds/categories"),
    load<Chart>("/finance/ledger/accounts"),
  ]);
  return (
    <>
      <PageHeader title="Expense categories">
        Requesters classify each expense in their liquidation under these, and Finance can reclassify it during review. Each category posts to an expense
        account in the chart of accounts. Only reimbursable categories are charged to the company; non-reimbursable expenses remain the employee&apos;s and are
        recovered through the refund.
      </PageHeader>
      <Sheet className="px-5 py-4">
        <CategoriesEditor categories={categories.items} accounts={chart.items} canEdit={categories.canEdit} />
      </Sheet>
    </>
  );
}
