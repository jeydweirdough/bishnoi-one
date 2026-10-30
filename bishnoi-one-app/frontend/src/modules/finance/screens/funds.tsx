import { ExternalLink, FileText } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { RowMenu } from "@/src/platform/ui/row-menu";
import { ListFrame, ListToolbar, UnderlineTabs } from "@/src/platform/ui/list-layout";
import { Empty, PageHeader, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat, type Format } from "@/src/modules/finance/platform/lib/format";
import { DownloadLink } from "@/src/modules/finance/exports/download-link";
import { CategoriesEditor } from "@/src/modules/finance/funds/categories-editor";
import type { Chart } from "@/src/modules/finance/ledger/types";
import type { ExpenseCategory, FundCounts, FundRequest } from "@/src/modules/finance/funds/types";

// Marketing requests: one page, with a tab for each stage (release, review, settle; the
// advances still out; settled and cancelled). Refunds and reimbursements are one settlement
// stage. The stage is in the address (?stage=…), so a tab can be linked to and bookmarked;
// the old sub-page addresses redirect here (stageRedirect).

export type FundTask = "to_release" | "to_check" | "to_settle" | "to_liquidate" | "history";

type Search = Promise<Record<string, string | string[] | undefined>>;

// A list shows this many requests; the download has all of them.
const LIST_LIMIT = 100;

const PAGE = "/finance/funds";

/** Each stage: its tab, the line saying what it is and who acts next, and the permission that acts on it (app/routers/funds.py). */
const STAGES: { key: FundTask; tab: string; says: string; acts: string | null; empty: string }[] = [
  {
    key: "to_release",
    tab: "To release",
    says: "Requests approved by the requester's Team Lead in the CRM, oldest first. Next: someone whose role may release cash advances releases it, or declines the release with a reason. A requester who still has an earlier advance to liquidate gets the next one only after that's liquidated.",
    acts: "funds.release",
    empty: "No requests for release.",
  },
  {
    key: "to_check",
    tab: "To review",
    says: "Liquidations the requester has submitted, oldest first. Next: someone whose role may review liquidations accepts or rejects each expense and completes the review, or returns it for correction. Whoever released the cash advance doesn't review its liquidation.",
    acts: "funds.check",
    empty: "No liquidations for review.",
  },
  {
    key: "to_settle",
    tab: "To settle",
    says: "Reviewed liquidations with a balance: a refund due from the employee, or a reimbursement due to them. Next: someone whose role may settle records the money returned or paid.",
    acts: "funds.settle",
    empty: "No liquidations for settlement.",
  },
  {
    key: "to_liquidate",
    tab: "Outstanding advances",
    says: "Cash advances released whose liquidation isn't in yet, overdue first. Next: the requester submits the liquidation; it then moves to To review.",
    acts: null,
    empty: "No outstanding cash advances.",
  },
  {
    key: "history",
    tab: "Settled and cancelled",
    says: "Settled and cancelled requests, newest first. Nothing more to do on these.",
    acts: null,
    empty: "No settled or cancelled requests yet.",
  },
];

const isStage = (v: unknown): v is FundTask => STAGES.some((s) => s.key === v);

/** How many are in each stage, from /finance/funds/counts. */
function countOf(counts: FundCounts & { to_settle: number }, stage: FundTask): number {
  if (stage === "history") return (counts.closed ?? 0) + (counts.cancelled ?? 0);
  return counts[stage] ?? 0;
}

/** The old address of one stage (/finance/funds/review and the like): to its tab, keeping the rest of the address's query. */
export async function stageRedirect(stage: FundTask, searchParams: Search): Promise<never> {
  const sp = await searchParams;
  const next = new URLSearchParams();
  for (const [key, value] of Object.entries(sp)) {
    if (key === "stage" || value === undefined) continue;
    for (const v of Array.isArray(value) ? value : [value]) next.append(key, v);
  }
  next.set("stage", stage);
  redirect(`${PAGE}?${next}`);
}

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

export default async function FundsPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const may = (p: string) => me.permissions?.includes(p) ?? false;
  const sp = await searchParams;
  const q = (typeof sp.q === "string" ? sp.q : "").trim().slice(0, 100);
  const asked = isStage(sp.stage) ? sp.stage : null;
  // The counts are the company's (the same as the sidebar's); "for you" is the stage your role acts on.
  const counts = await load<FundCounts & { to_settle: number }>("/finance/funds/counts");
  // No stage asked: the first one with something your role can act on; otherwise the settled and cancelled.
  const task: FundTask = asked ?? STAGES.find((s) => s.acts && may(s.acts) && countOf(counts, s.key) > 0)?.key ?? "history";
  const t = STAGES.find((s) => s.key === task)!;
  const shown = new URLSearchParams({ task });
  if (q) shown.set("q", q);
  const list = await load<{ items: FundRequest[] }>(`/finance/funds?${shown}&limit=${LIST_LIMIT}`);
  const items = task === "to_liquidate" ? [...list.items].sort((a, b) => Number(b.overdue) - Number(a.overdue)) : list.items;
  // Where more than one status shares a stage, each row says which.
  const mixed = task === "to_settle" || task === "history";
  const here = `${PAGE}?stage=${task}`;
  return (
    <>
      <PageHeader title="Marketing requests">
        Cash advances for marketing, approved by the requester&apos;s Team Lead in the CRM. Finance releases the cash advance, the requester liquidates it,
        Finance reviews the liquidation and settles any balance. Each tab is one stage, with how many are in it.
      </PageHeader>
      <ListFrame>
        <UnderlineTabs
          label="Stage"
          tabs={STAGES.map((s) => ({ href: `${PAGE}?stage=${s.key}`, label: s.tab, count: countOf(counts, s.key), current: s.key === task }))}
        />
        <p className="border-b border-rule px-5 py-3 text-sm text-ink-2">
          {t.says}
          {t.acts && may(t.acts) && " Your role can do this."}
          {task === "to_liquidate" && counts.overdue > 0 && <span className="font-medium text-danger"> {counts.overdue} overdue.</span>}
        </p>
        <ListToolbar q={q} placeholder="Number, requester, purpose or customer" keep={{ stage: task }}>
          {q && (
            <Link href={here} className="text-meta text-hema hover:underline">
              Clear search
            </Link>
          )}
          <DownloadLink href={`/finance/funds/export?${shown}`} />
        </ListToolbar>
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
          <ul className="divide-y divide-rule border-t border-rule">
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
      </ListFrame>
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
