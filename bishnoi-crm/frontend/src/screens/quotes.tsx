import { Users } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { QuoteStateMark } from "@/src/platform/ui/marks";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { Later } from "@/src/platform/ui/later";
import { ListRows } from "@/src/platform/ui/skeleton";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { CompanyRow, Paged, Quote } from "@/src/platform/lib/types";
import { NewQuoteButton } from "../components/crm/new-quote-button";
import { NoAccess } from "../components/admin/words";
import { Filters, Pager } from "../components/crm/list-controls";

export const metadata = { title: "Quotes" };

const SIZE = 50;
// What's waiting on an approver, or on Finance's credit confirmation: each a list of its own, for those who decide it.
const TASKS = [
  { key: "credit", label: "Credit to confirm", empty: "No B2B quotes waiting for a credit confirmation.", permission: "orders.credit" },
  { key: "approvals", label: "To approve", empty: "Nothing waiting for approval." },
  { key: "letters", label: "Letters to check", empty: "No guarantee letters waiting to be checked." },
  { key: "payments", label: "Letter payments", empty: "No verified letters waiting on payment." },
] as const;

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export default async function QuotesPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "quotes.view")) return <NoAccess what="quotes" />;
  const fmt = makeFormat(me.org);
  const params = await searchParams;
  // The lists this person decides: approvals, letters and payments for an approver; credit for Finance.
  const tasks = TASKS.filter((t) => ("permission" in t ? can(me, t.permission) : can(me, "quotes.approve")));
  const approver = tasks.length > 0;
  const task = tasks.find((t) => t.key === one(params.task));
  const [q, state, owner] = [one(params.q), one(params.state), one(params.owner)];
  const page = Math.max(1, Number(one(params.page)) || 1);
  const query = new URLSearchParams({ limit: String(SIZE), offset: String((page - 1) * SIZE) });
  for (const [k, v] of Object.entries({ task: task?.key ?? "", q, state, owner })) if (v) query.set(k, v);

  const quotes = can(me, "quotes.create");
  // Asked for, not waited on: the title, tabs, filters and list card are drawn now and the rest fills in.
  const listing = load<Paged<Quote>>(`/quotes?${query}`);
  const customers = quotes && can(me, "customers.view") ? load<Paged<CompanyRow>>("/companies?limit=200") : Promise.resolve({ items: [], total: 0 } as Paged<CompanyRow>);
  const waiting = Promise.all(approver ? tasks.map((t) => load<Paged<Quote>>(`/quotes?task=${t.key}&limit=1`)) : []);
  const tab = (key: string) => (key ? `/quotes?task=${key}` : "/quotes");
  const chip = (key: string, label: string, count?: number) => {
    const current = (task?.key ?? "") === key;
    return (
      <Link
        key={key || "all"}
        href={tab(key)}
        aria-current={current ? "page" : undefined}
        className={`rounded-md border px-3 py-1 text-meta ${
          current ? "border-hema bg-hema-tint font-semibold text-ink" : "border-rule-strong bg-sheet text-ink-2 hover:border-hema hover:text-ink"
        }`}
      >
        {label}
        {count ? <span className="text-ink-3"> {count}</span> : null}
      </Link>
    );
  };
  const here = new URLSearchParams(Object.entries({ task: task?.key ?? "", q, state, owner }).filter(([, v]) => v));
  const pickerOf = (c: Paged<CompanyRow>) => (quotes ? c.items.map((x) => ({ id: x.id, name: x.name })) : null);
  const chips = (counts: Paged<Quote>[]) => (
    <nav aria-label="Show" className="mb-4 flex flex-wrap gap-1.5">
      {chip("", "All quotes")}
      {tasks.map((t, i) => chip(t.key, t.label, counts[i]?.total))}
    </nav>
  );

  return (
    <>
      <PageHeader
        title="Quotes"
        actions={
          quotes && (
            <Later data={customers} fallback={null}>
              {(c) => <NewQuoteButton customers={pickerOf(c)!} />}
            </Later>
          )
        }
      >
        {task ? (task.key === "credit" ? "B2B quotes waiting for you to confirm the customer's credit status." : "Waiting on you as an approver.") : "Every quote you can see, newest first."}
      </PageHeader>

      {approver && (
        <Later data={waiting} fallback={chips([])}>
          {chips}
        </Later>
      )}

      <Filters
        search="Number or customer"
        selects={[
          ...(task
            ? []
            : [
                {
                  name: "state",
                  label: "State",
                  options: [
                    { value: "", label: "Any state" },
                    { value: "waiting", label: "Waiting for approval" },
                    { value: "ready", label: "Ready" },
                    { value: "rejected", label: "Rejected" },
                  ],
                },
              ]),
          ...(me.role?.scope !== "own"
            ? [{ name: "owner", label: "Owner", options: [{ value: "", label: "All" }, { value: "me", label: "Created by me" }] }]
            : []),
        ]}
      />

      <Later
        data={Promise.all([listing, customers])}
        fallback={
          <Sheet className="overflow-hidden">
            <ListRows columns={2} />
          </Sheet>
        }
      >
        {([list, c]) => {
          const picker = pickerOf(c);
          return (
            <>
              <Sheet className="overflow-hidden">
                {list.items.length === 0 ? (
                  <Empty
                    icon="quotes"
                    title={task ? task.empty : q || state || owner ? "No quotes match." : "No quotes yet."}
                    actions={
                      q || state || owner ? (
                        <LinkButton href={tab(task?.key ?? "")} variant="default">
                          Clear filters
                        </LinkButton>
                      ) : (
                        !task &&
                        picker && (
                          <>
                            <NewQuoteButton customers={picker} label="Create first quote" />
                            <LinkButton href="/companies" variant="quiet" icon={<Users className="size-4" aria-hidden />}>
                              Go to customers
                            </LinkButton>
                          </>
                        )
                      )
                    }
                  >
                    {!task && !q && !state && !owner && "A quote is always for a customer: pick one, then add the products."}
                  </Empty>
                ) : (
                  <ul className="divide-y divide-rule">
                    {list.items.map((x) => (
                      <li key={x.id} className="flex items-start justify-between gap-4 px-5 py-3">
                        <div className="min-w-0">
                          <Link href={`/quotes/${x.id}${task ? `?from=${task.key}` : ""}`} className="font-semibold text-ink hover:underline">
                            {x.number}
                          </Link>
                          <span className="text-ink-2"> · {x.customerName}</span>
                          <p className="text-meta text-ink-3">
                            {[
                              fmt.whenLabel(x.createdAt),
                              x.priceTypeName + (x.rx ? " · Rx" : ""),
                              x.payerName && `${x.payerName} letter`,
                              x.createdBy.id === me.user.id ? "by you" : `by ${x.createdBy.name}`,
                            ]
                              .filter(Boolean)
                              .join(" · ")}
                          </p>
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-1">
                          <span className="font-semibold tabular-nums">{fmt.peso(x.totalCentavos)}</span>
                          {task?.key === "payments" && x.letter ? (
                            <span className="text-meta text-ink-2">
                              {fmt.peso(x.payment.paidCentavos)} of {fmt.peso(x.letter.amountCentavos)} paid
                            </span>
                          ) : (
                            <QuoteStateMark state={x.state} />
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Sheet>
              <Pager total={list.total} page={page} size={SIZE} base={`/quotes${here.size ? `?${here}` : ""}`} />
            </>
          );
        }}
      </Later>
    </>
  );
}
