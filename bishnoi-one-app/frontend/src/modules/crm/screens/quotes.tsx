import { Building2, ExternalLink, Printer, Trash2, Users } from "lucide-react";
import { RowMenu } from "@/src/platform/ui/row-menu";
import { deleteQuote } from "@/src/modules/crm/actions/customers";
import { Board as KanbanBoard } from "@/src/platform/ui/board";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { ListViews } from "@/src/modules/crm/components/crm/list-views";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { QuoteStateMark } from "@/src/platform/ui/marks";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { Later } from "@/src/platform/ui/later";
import { ListRows } from "@/src/platform/ui/skeleton";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { CompanyRow, Paged, Quote } from "@/src/platform/lib/types";
import { NewQuoteButton } from "@/src/modules/crm/components/crm/new-quote-button";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { Filters, Pager } from "@/src/modules/crm/components/crm/list-controls";
import { ListFrame, StatusPill, UnderlineTabs, type PillTone } from "@/src/platform/ui/list-layout";
import { ExpandableTable } from "@/src/platform/ui/expandable-table";

export const metadata = { title: "Quotes" };

const SIZE = 50;
const BOARD_SIZE = 200;
// What's waiting on an approver, or on Finance's credit confirmation: each a list of its own, for those who decide it.
const TASKS = [
  { key: "credit", label: "Credit to confirm", empty: "No B2B quotes waiting for a credit confirmation.", permission: "orders.credit" },
  { key: "approvals", label: "To approve", empty: "Nothing waiting for approval." },
  { key: "letters", label: "Letters to check", empty: "No guarantee letters waiting to be checked." },
  { key: "payments", label: "Letter payments", empty: "No verified letters waiting on payment." },
] as const;

/** Where a quote stands, as one word: ordered, credit on hold, or its approval state. */
function standing(x: Quote): { tone: PillTone; label: string } {
  if (x.order) return { tone: "info", label: "Ordered" };
  if (x.credit?.decision === "hold") return { tone: "bad", label: "Credit on hold" };
  if (x.state === "ready") return { tone: "good", label: "Ready" };
  if (x.state === "rejected") return { tone: "bad", label: "Rejected" };
  return { tone: "warn", label: "Waiting for approval" };
}

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
  // As a table (paged), or as a board by state (benchmark E1): the board shows the newest BOARD_SIZE.
  const layout = one(params.layout) === "board" ? "board" : "table";
  const query = new URLSearchParams(layout === "board" ? { limit: String(BOARD_SIZE), offset: "0" } : { limit: String(SIZE), offset: String((page - 1) * SIZE) });
  for (const [k, v] of Object.entries({ task: task?.key ?? "", q, state, owner })) if (v) query.set(k, v);

  const quotes = can(me, "quotes.create");
  // Asked for, not waited on: the title, tabs, filters and list card are drawn now and the rest fills in.
  const listing = load<Paged<Quote>>(`/quotes?${query}`);
  const customers = quotes && can(me, "customers.view") ? load<Paged<CompanyRow>>("/companies?limit=200") : Promise.resolve({ items: [], total: 0 } as Paged<CompanyRow>);
  const waiting = Promise.all(approver ? tasks.map((t) => load<Paged<Quote>>(`/quotes?task=${t.key}&limit=1`)) : []);
  const tab = (key: string) => (key ? `/crm/quotes?task=${key}` : "/crm/quotes");
  const here = new URLSearchParams(Object.entries({ task: task?.key ?? "", q, state, owner }).filter(([, v]) => v));
  const layoutHref = (l: string) => {
    const next = new URLSearchParams(here);
    if (l === "board") next.set("layout", "board");
    return `/crm/quotes${next.size ? `?${next}` : ""}`;
  };
  const pickerOf = (c: Paged<CompanyRow>) => (quotes ? c.items.map((x) => ({ id: x.id, name: x.name })) : null);
  const tabsOf = (counts: Paged<Quote>[]) => [
    { href: tab(""), label: "All quotes", current: !task },
    ...tasks.map((t, i) => ({ href: tab(t.key), label: t.label, count: counts[i]?.total, current: task?.key === t.key })),
  ];

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
      <ListViews list="quotes" />

      <ListFrame>
        {approver && (
          <Later data={waiting} fallback={<UnderlineTabs tabs={tabsOf([])} />}>
            {(counts) => <UnderlineTabs tabs={tabsOf(counts)} />}
          </Later>
        )}
        {/* One toolbar row: the live search and filters, the table or board on the right. */}
        <div className="flex flex-wrap items-end justify-between gap-3 px-5 pt-3 pb-3 [&_.mb-4]:mb-0">
          <div className="min-w-0 flex-1">
            <Filters
              search="Search number or customer"
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
          </div>
          <ToggleLinks
            current={layout}
            options={[
              { value: "table", label: "Table", href: layoutHref("table") },
              { value: "board", label: "Board", href: layoutHref("board") },
            ]}
          />
        </div>

        <Later data={Promise.all([listing, customers])} fallback={<ListRows columns={2} />}>
          {([list, c]) => {
            if (layout === "board") return <div className="border-t border-rule p-4"><QuotesBoard list={list} fmt={fmt} task={task?.key} /></div>;
            const picker = pickerOf(c);
            if (list.items.length === 0)
              return (
                <div className="border-t border-rule">
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
                            <LinkButton href="/crm/customers" variant="quiet" icon={<Users className="size-4" aria-hidden />}>
                              Go to customers
                            </LinkButton>
                          </>
                        )
                      )
                    }
                  >
                    {!task && !q && !state && !owner && "A quote is always for a customer: pick one, then add the products."}
                  </Empty>
                </div>
              );
            return (
              <div className="border-t border-rule">
                <ExpandableTable
                  minWidth="50rem"
                  columns={[
                    { key: "number", label: "Quote" },
                    { key: "customer", label: "Customer" },
                    { key: "made", label: "Created" },
                    { key: "price", label: "Price type" },
                    { key: "total", label: "Total", align: "right" },
                    { key: "state", label: task?.key === "payments" ? "Letter paid" : "Status" },
                  ]}
                  rows={list.items.map((x) => {
                    const st = standing(x);
                    return {
                      id: x.id,
                      muted: x.state === "rejected",
                      actions: (
                        <RowMenu
                          label={`Actions for quote ${x.number}`}
                          items={[
                            { label: "Open", icon: <ExternalLink />, href: `/crm/quotes/${x.id}${task ? `?from=${task.key}` : ""}` },
                            { label: "Print", icon: <Printer />, href: `/crm/print/quotes/${x.id}` },
                            ...(x.customerHref ? ["divider" as const, { label: "Open customer", icon: <Building2 />, href: x.customerHref }] : []),
                            ...(x.can.delete
                              ? [
                                  "divider" as const,
                                  {
                                    label: "Delete",
                                    icon: <Trash2 />,
                                    run: deleteQuote.bind(null, x.id),
                                    danger: true,
                                    confirm: `Delete quote ${x.number}? This can't be undone.`,
                                    done: `Quote ${x.number} deleted`,
                                  },
                                ]
                              : []),
                          ]}
                        />
                      ),
                      cells: [
                        <Link key="n" href={`/crm/quotes/${x.id}${task ? `?from=${task.key}` : ""}`} className="font-mono text-meta font-semibold text-ink hover:text-sage-deep hover:underline">{x.number}</Link>,
                        <span key="c" className="min-w-0">
                          <span className="block truncate font-medium text-ink">{x.customerName}</span>
                          <span className="block truncate text-meta text-ink-3">{x.createdBy.id === me.user.id ? "By you" : `By ${x.createdBy.name}`}{x.payerName ? ` · ${x.payerName} letter` : ""}</span>
                        </span>,
                        <span key="m" className="text-ink-2">{fmt.whenLabel(x.createdAt)}</span>,
                        <span key="p" className="text-ink-2">{x.priceTypeName}{x.rx ? " · Rx" : ""}</span>,
                        <span key="t" className="font-medium">{fmt.peso(x.totalCentavos)}</span>,
                        task?.key === "payments" && x.letter ? (
                          <span key="s" className="text-meta text-ink-2">{fmt.peso(x.payment.paidCentavos)} of {fmt.peso(x.letter.amountCentavos)}</span>
                        ) : (
                          <StatusPill key="s" tone={st.tone}>{st.label}</StatusPill>
                        ),
                      ],
                      detail: (
                        <div className="space-y-3">
                          <table className="w-full text-meta">
                            <thead>
                              <tr className="text-left text-ink-3">
                                <th className="py-1 pr-3 font-medium">Code</th>
                                <th className="px-3 py-1 font-medium">Product</th>
                                <th className="px-3 py-1 text-right font-medium">Quantity</th>
                                <th className="px-3 py-1 text-right font-medium">Unit price</th>
                                <th className="py-1 pl-3 text-right font-medium">Amount</th>
                              </tr>
                            </thead>
                            <tbody>
                              {x.lines.map((l, i) => (
                                <tr key={`${l.productId || l.bundleId}-${i}`} className="border-t border-rule/70">
                                  <td className="py-1.5 pr-3 font-mono text-ink-2">{l.productCode}</td>
                                  <td className="px-3 py-1.5 text-ink">
                                    {l.bundleName ?? l.productName}
                                    {l.promoName && <span className="text-ink-3"> · {l.promoName}</span>}
                                  </td>
                                  <td className="px-3 py-1.5 text-right tabular-nums">
                                    {l.quantity} {l.unit}
                                    {l.freeQuantity ? <span className="text-sage-deep"> +{l.freeQuantity} free</span> : null}
                                  </td>
                                  <td className="px-3 py-1.5 text-right tabular-nums text-ink-2">{fmt.peso(l.unitPriceCentavos)}</td>
                                  <td className="py-1.5 pl-3 text-right font-medium tabular-nums">{fmt.peso(l.totalCentavos)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule/70 pt-3">
                            <p className="text-meta text-ink-2">
                              {x.credit ? (
                                <>
                                  Credit: <strong className="text-ink">{x.credit.label}</strong>
                                  {x.credit.decision ? ` · Finance ${x.credit.decision === "hold" ? "put it on hold" : "confirmed it"}` : " · waiting for Finance"}
                                </>
                              ) : x.letter ? (
                                <>Guarantee letter: <strong className="text-ink">{fmt.peso(x.letter.amountCentavos)}</strong></>
                              ) : (
                                <>Total <strong className="text-ink tabular-nums">{fmt.peso(x.totalCentavos)}</strong></>
                              )}
                            </p>
                            <LinkButton href={`/crm/quotes/${x.id}${task ? `?from=${task.key}` : ""}`}>Open quote</LinkButton>
                          </div>
                        </div>
                      ),
                    };
                  })}
                />
                <div className="border-t border-rule px-5 py-3">
                  <Pager total={list.total} page={page} size={SIZE} base={`/crm/quotes${here.size ? `?${here}` : ""}`} />
                </div>
              </div>
            );
          }}
        </Later>
      </ListFrame>
    </>
  );
}


// Where a quote stands, left to right: waiting on someone, ready to order, ordered, rejected.
const QUOTE_COLUMNS = [
  { key: "waiting", label: "Waiting for approval", hint: "Nothing waiting" },
  { key: "ready", label: "Ready", hint: "Nothing ready to order" },
  { key: "ordered", label: "Ordered", hint: "Nothing ordered yet" },
  { key: "rejected", label: "Rejected", hint: "Nothing rejected" },
];

/**
 * Quotes as a board by where they stand (benchmark E1, after Twenty). Read-only:
 * approving, checking a letter and ordering each have their own step on the
 * quote, so a card opens the quote rather than being dragged.
 */
function QuotesBoard({ list, fmt, task }: { list: Paged<Quote>; fmt: ReturnType<typeof makeFormat>; task?: string }) {
  const columnOf = (x: Quote) => (x.order ? "ordered" : x.state);
  return (
    <>
      {list.total > list.items.length && (
        <p className="mb-2 text-meta text-ink-3">
          The newest {list.items.length} of {list.total}. Search or filter to narrow it down.
        </p>
      )}
      <KanbanBoard
        columns={QUOTE_COLUMNS.map((col) => {
          const here = list.items.filter((x) => columnOf(x) === col.key);
          return { ...col, note: `${fmt.plural(here.length, "quote")} · ${fmt.pesoCompact(here.reduce((n, x) => n + x.totalCentavos, 0))}` };
        })}
        cards={list.items.map((x) => ({
          id: x.id,
          column: columnOf(x),
          href: `/crm/quotes/${x.id}${task ? `?from=${task}` : ""}`,
          title: x.number,
          sub: x.customerName ?? undefined,
          value: fmt.peso(x.totalCentavos),
          when: fmt.whenLabel(x.createdAt),
          meta: [x.priceTypeName, x.credit?.decision === "hold" ? "Credit on hold" : null, x.createdBy.name].filter(Boolean).join(" · "),
          movable: false,
        }))}
        moves={[]}
        run={async () => ({ ok: false as const, error: "Open the quote to move it on." })}
      />
    </>
  );
}
