import { ExternalLink, FileText } from "lucide-react";
import Link from "next/link";
import { RowMenu } from "@/src/platform/ui/row-menu";
import { buttonClass } from "@/src/modules/finance/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat, type Format } from "@/src/modules/finance/platform/lib/format";
import { DownloadLink } from "@/src/modules/finance/exports/download-link";
import { CategoriesEditor } from "@/src/modules/finance/funds/categories-editor";
import type { Chart } from "@/src/modules/finance/ledger/types";
import type { ExpenseCategory, FundRequest } from "@/src/modules/finance/funds/types";

// Marketing requests, by what Finance does next: release, review, settle. Refunds
// and reimbursements are one settlement queue; settled and cancelled requests
// are one history. Each is a sub-page of Marketing requests in the sidebar.

export type FundTask = "to_release" | "to_check" | "to_settle" | "to_liquidate" | "history";

type Search = Promise<Record<string, string | string[] | undefined>>;

// A list shows this many requests; the download has all of them.
const LIST_LIMIT = 100;

const TASKS: Record<FundTask, { path: string; title: string; intro: string; empty: string }> = {
  to_release: {
    path: "/finance/funds",
    title: "For release",
    intro: "Requests approved by the requester's Team Lead in the CRM, oldest first. Release the cash advance, or decline the release with a reason.",
    empty: "No requests for release.",
  },
  to_check: {
    path: "/finance/funds/review",
    title: "For review",
    intro: "Submitted liquidations, oldest first. Accept or reject each expense, then complete the review.",
    empty: "No liquidations for review.",
  },
  to_settle: {
    path: "/finance/funds/settlement",
    title: "For settlement",
    intro: "Reviewed liquidations with a balance: a refund due from the employee, or a reimbursement due to them.",
    empty: "No liquidations for settlement.",
  },
  to_liquidate: {
    path: "/finance/funds/outstanding",
    title: "Outstanding",
    intro: "Cash advances released and not yet liquidated. Overdue items first.",
    empty: "No outstanding cash advances.",
  },
  history: {
    path: "/finance/funds/history",
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

export default async function FundsPage({ task, searchParams }: { task: FundTask; searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const t = TASKS[task];
  const sp = await searchParams;
  const q = (typeof sp.q === "string" ? sp.q : "").trim().slice(0, 100);
  const shown = new URLSearchParams({ task });
  if (q) shown.set("q", q);
  const list = await load<{ items: FundRequest[] }>(`/finance/funds?${shown}&limit=${LIST_LIMIT}`);
  const items = task === "to_liquidate" ? [...list.items].sort((a, b) => Number(b.overdue) - Number(a.overdue)) : list.items;
  // Where more than one status shares a page, each row says which.
  const mixed = task === "to_settle" || task === "history";
  return (
    <>
      <PageHeader title={t.title} actions={<DownloadLink href={`/finance/funds/export?${shown}`} />}>
        {t.intro}
      </PageHeader>
      <form className="mb-4 flex flex-wrap items-end gap-3" action={t.path} role="search">
        <label className="text-meta text-ink-2">
          Search
          <input suppressHydrationWarning
            type="search"
            name="q"
            defaultValue={q}
            maxLength={100}
            placeholder="Number, requester, purpose or customer"
            className="ml-2 h-8 w-72 rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm"
          />
        </label>
        <button suppressHydrationWarning type="submit" className={buttonClass("default", "sm")}>
          Search
        </button>
        {q && (
          <Link href={t.path} className="text-meta text-hema hover:underline">
            Clear
          </Link>
        )}
      </form>
      <Sheet>
        {items.length === 0 ? (
          q ? (
            <Empty title="No requests match" icon="payments">
              Nothing here matches &ldquo;{q}&rdquo;. Try a request number or the requester&apos;s name.
            </Empty>
          ) : (
            <Empty title={t.empty} icon="payments">
              Requests arrive from the CRM once a Team Lead approves them.
            </Empty>
          )
        ) : (
          <ul className="divide-y divide-rule">
            {items.map((r) => (
              <li key={r.id} className="flex items-center gap-2 pr-3 hover:bg-bench/60">
                <Link href={`/finance/funds/${r.id}`} className="flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-1 py-3 pl-5">
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
                <RowMenu
                  label={`Actions for ${r.number}`}
                  items={[
                    { label: "Open", icon: <ExternalLink />, href: `/finance/funds/${r.id}` },
                    ...(r.checkedAt ? [{ label: "Liquidation report", icon: <FileText />, href: `/finance/funds/${r.id}/report` }] : []),
                  ]}
                />
              </li>
            ))}
          </ul>
        )}
      </Sheet>
      {items.length === LIST_LIMIT && (
        <p className="mt-2 px-1 text-meta text-ink-3">
          Showing the first {LIST_LIMIT} requests. Search to narrow the list, or download the CSV for all of them.
        </p>
      )}
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
