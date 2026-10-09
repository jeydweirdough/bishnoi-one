import Link from "next/link";
import { FollowUpItem } from "../components/follow-up-item";
import { NewCustomerButton } from "../components/crm/new-customer";
import { Icon } from "@/src/platform/ui/icons";
import { QuoteStateMark } from "@/src/platform/ui/marks";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { AttentionPanel } from "../components/attention-panel";
import { getCompanyMe, query } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { ActivityItem, ActivitySummary, Assignable, CompanyRow, DealList, DealSummary, KpiScorecard, Paged, Quote, SalesResults } from "@/src/platform/lib/types";
import type { Figure } from "../components/deals/figure-card";
import { StageTag } from "../components/deals/words";
import { YourMonth } from "../components/kpis/performance";
import { customerOf, dayOf, followUpRow } from "../components/crm/follow-up-rows";
import { LogActivityButton } from "../components/crm/log-activity-button";
import { MonthTarget } from "../components/deals/month-target";
import { kindOf } from "../components/crm/words";



/** Where the day starts: what's due, what needs a hand, and what just happened. */
export async function SalespersonHome() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const seesActivities = can(me, "activities.view");
  const seesQuotes = can(me, "quotes.view");
  const approver = can(me, "quotes.approve");
  const none: Paged<never> = { items: [], total: 0 };
  const logs = can(me, "activities.create");
  const seesDeals = can(me, "deals.view");
  // Home's one request. The customers are for the "log a call" picker, so only their names.
  const { data } = await query<{
    counts?: ActivitySummary | null;
    mine?: Paged<ActivityItem> | null;
    recent?: Paged<ActivityItem> | null;
    myQuotes?: Paged<Quote> | null;
    toApprove?: Paged<Quote> | null;
    people?: Assignable[] | null;
    companies?: { items: Pick<CompanyRow, "id" | "name">[]; total: number } | null;
    performance?: KpiScorecard | null;
    trend?: { points: { month: string; quotedCentavos: number; newCustomers: number }[] } | null;
    results?: SalesResults | null;
    pipeline?: DealSummary | null;
    deals?: DealList | null;
  }>(
    `query RepHome($activities: Boolean!, $quotes: Boolean!, $approver: Boolean!, $logs: Boolean!, $customers: Boolean!, $deals: Boolean!) {
      counts: activitySummary(owner: "me") @include(if: $activities)
      mine: activities(owner: "me", state: "open", limit: 100) @include(if: $activities)
      recent: activities(state: "done", limit: 8) @include(if: $activities)
      myQuotes: quotes(owner: "me", limit: 6) @include(if: $quotes)
      toApprove: quotes(task: "approvals", limit: 1) @include(if: $approver)
      people @include(if: $logs) { id name isMe team { id name } }
      companies(limit: 200) @include(if: $customers) { total items { id name } }
      performance(view: "mine")
      trend: salesTrend(months: 2, view: "mine") @include(if: $deals)
      results: salesResults(view: "mine") @include(if: $deals)
      pipeline: dealsSummary(state: "open", owner: "me") @include(if: $deals)
      deals(owner: "me", state: "open", sort: "close", limit: 5) @include(if: $deals)
    }`,
    { activities: seesActivities, quotes: seesQuotes, approver, logs, customers: logs && can(me, "customers.view"), deals: seesDeals },
  );
  const counts = data.counts ?? { overdue: 0, today: 0, upcoming: 0, open: 0 };
  const mine = data.mine ?? none;
  const recent = data.recent ?? none;
  const myQuotes = data.myQuotes ?? none;
  const toApprove = data.toApprove ?? none;
  const people = data.people ?? [];
  const companies = data.companies ?? none;
  const measured = (data.performance?.kpis ?? []).some((k) => data.performance?.people[0]?.results[k.id]);
  // The rest of the month, each figure once: what isn't already a measure.
  const measures = new Set((data.performance?.kpis ?? []).filter((k) => data.performance?.people[0]?.results[k.id]).map((k) => k.measure));
  const [lastMonth, thisMonth] = data.trend?.points.slice(-2) ?? [];
  const change = (now: number, before: number) => (before ? `${now >= before ? "+" : "−"}${Math.abs(Math.round((100 * (now - before)) / before))}% on last month` : "Nothing last month");
  const pipe = data.pipeline;
  const totals = data.results?.totals;
  const decided = totals ? totals.wonCount + totals.lostCount : 0;
  const more: Figure[] = [
    ...(pipe
      ? [{ value: fmt.peso(pipe.valueCentavos), label: "Open pipeline", note: pipe.count ? `${fmt.plural(pipe.count, "open deal")} · ${fmt.peso(pipe.weightedCentavos)} weighted` : "No open deals yet", ring: pipe.valueCentavos ? Math.round((100 * pipe.weightedCentavos) / pipe.valueCentavos) : null, href: "/deals?who=me" }]
      : []),
    ...(thisMonth && !measures.has("quotes_value")
      ? [{ value: fmt.peso(thisMonth.quotedCentavos), label: "Quoted", note: lastMonth ? change(thisMonth.quotedCentavos, lastMonth.quotedCentavos) : "So far", href: "/quotes?owner=me" }]
      : []),
    ...(thisMonth && !measures.has("new_customers")
      ? [{ value: String(thisMonth.newCustomers), label: "New customers", note: lastMonth ? `Last month ${lastMonth.newCustomers}` : "So far", href: "/companies" }]
      : []),
    ...(totals
      ? [{ value: totals.winRate === null ? "—" : `${totals.winRate}%`, label: "Win rate", note: decided ? `${fmt.plural(totals.wonCount, "deal")} won, ${totals.lostCount} lost` : "No deals decided yet", ring: totals.winRate, href: "/deals?view=closed&who=me" }]
      : []),
  ];
  const closing = data.deals?.items ?? [];
  const monthShown = measured || seesDeals;
  const today = dayOf(new Date().toISOString(), me.org.timezone);
  // Due now: overdue first, then today. What's further ahead waits in Activities.
  const due = mine.items.map((a) => followUpRow(a, today, me.org.timezone)).filter((f) => f.bucket === "overdue" || f.bucket === "today");
  const needsHand = myQuotes.items.filter((q) => q.state !== "ready");

  return (
    <>
      <PageHeader
        title="Home"
        actions={
          <>
            {can(me, "customers.create") && (
<NewCustomerButton variant="default" />
            )}
            {can(me, "activities.create") && (
              <LogActivityButton
                variant="primary"
                org={me.org}
                now={new Date().toISOString()}
                people={people}
                companies={companies.items.map((c) => ({ id: c.id, name: c.name }))}
              />
            )}
          </>
        }
      >
        {fmt.greeting()}, {me.user.fullName.split(" ")[0]}. {me.role?.name}
        {me.team ? ` · ${me.team.name}` : ""}
      </PageHeader>
      {/* What needs you now: the prompts (the month's own target is in Your month, so not again here). */}
      <AttentionPanel skip={monthShown ? ["target"] : []} />

      {/* Then the day's work, widest; beside it, how the month is going, one card. */}
      <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex flex-col">
          {seesActivities && (
            <Sheet className="flex-1 px-5 pt-4 pb-2">
              <SectionTitle
                icon="followUps"
                action={
                  <Link href="/activities" className="text-meta font-medium text-ink hover:underline">
                    All to do
                  </Link>
                }
              >
                Your to do
              </SectionTitle>
              <p className="text-meta text-ink-3">
                <span className={counts.overdue ? "font-semibold text-danger" : ""}>{counts.overdue} overdue</span> · {counts.today} today ·{" "}
                {counts.upcoming} coming up
              </p>
              {due.length === 0 ? (
                <Empty icon="followUps" title="Nothing due today" actions={can(me, "activities.create") && <LogActivityButton
                      label="Plan a follow-up"
                      org={me.org}
                      now={new Date().toISOString()}
                      people={people}
                      companies={companies.items.map((c) => ({ id: c.id, name: c.name }))}
                    />}>
                  {counts.upcoming ? `${counts.upcoming} coming up later. ` : ""}Meetings and tasks you plan show up here on the day.
                </Empty>
              ) : (
                <ul className="divide-y divide-rule">
                  {due.map((f) => (
                    <FollowUpItem key={f.id} today={today} row={f} org={me.org} />
                  ))}
                </ul>
              )}
            </Sheet>
          )}

        </div>
        <div className="flex flex-col">
          <YourMonth card={data.performance ?? null} more={more} fmt={fmt} month={today.slice(0, 7)} />
          {!measured && can(me, "deals.view") && <MonthTarget view="mine" fmt={fmt} today={today} mayTarget={can(me, "goals.manage")} />}
        </div>
      </div>

      {/* Then the rest: deals and quotes in hand, and what just happened. */}
      <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
        <div className="space-y-5">
          {seesDeals && (
            <Sheet className="px-5 pt-4 pb-2">
              <SectionTitle
                icon="deals"
                action={
                  <Link href="/deals?who=me" className="text-meta font-medium text-ink hover:underline">
                    All your deals
                  </Link>
                }
              >
                Your deals closing next
              </SectionTitle>
              {closing.length === 0 ? (
                <Empty compact icon="deals" art="steps" title="No open deals">
                  A deal on a customer shows here until it&apos;s won or lost, soonest to close first.
                </Empty>
              ) : (
                <ul className="divide-y divide-rule">
                  {closing.map((d) => (
                    <li key={d.id} className="flex items-center justify-between gap-3 py-2.5">
                      <span className="min-w-0">
                        <Link href={`/deals/${d.id}`} className="font-medium text-ink hover:underline">
                          {d.name}
                        </Link>
                        <span className="block truncate text-meta text-ink-3">
                          {d.company.name} · closes {fmt.dateLabel(d.expectedCloseOn)}
                        </span>
                      </span>
                      <span className="flex shrink-0 flex-col items-end gap-0.5">
                        <span className="text-sm tabular-nums">{fmt.peso(d.valueCentavos)}</span>
                        <StageTag deal={d} />
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Sheet>
          )}
          {seesQuotes && (
            <Sheet className="px-5 pt-4 pb-2">
              <SectionTitle
                icon="quotes"
                action={
                  <Link href="/quotes?owner=me" className="text-meta font-medium text-ink hover:underline">
                    All your quotes
                  </Link>
                }
              >
                Your quotes
              </SectionTitle>
              {approver && toApprove.total > 0 && (
                <Link href="/quotes?task=approvals" className="mt-1 flex items-center justify-between rounded-[14px] bg-hema-tint px-3 py-2 text-sm font-medium text-ink hover:underline">
                  {toApprove.total} {toApprove.total === 1 ? "quote is" : "quotes are"} waiting for your approval
                  <span aria-hidden>→</span>
                </Link>
              )}
              {needsHand.length === 0 ? (
                myQuotes.total ? (
                  <p className="py-3 text-meta text-ink-3">None waiting or rejected.</p>
                ) : (
                  <Empty compact icon="quotes" title="No quotes yet">Make one from a customer&apos;s page, or with New quote.</Empty>
                )
              ) : (
                <ul className="divide-y divide-rule">
                  {needsHand.map((q) => (
                    <li key={q.id} className="flex items-center justify-between gap-3 py-2.5">
                      <span className="min-w-0">
                        <Link href={`/quotes/${q.id}`} className="font-medium text-ink hover:underline">
                          {q.number}
                        </Link>
                        <span className="block truncate text-meta text-ink-3">{q.customerName}</span>
                      </span>
                      <span className="flex shrink-0 flex-col items-end gap-0.5">
                        <span className="text-sm tabular-nums">{fmt.peso(q.totalCentavos)}</span>
                        <QuoteStateMark state={q.state} />
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Sheet>
          )}

        </div>
        <Sheet className="px-5 pt-4 pb-2">
          <SectionTitle
            icon="activity"
            action={
              seesActivities && (
                <Link href="/activities?view=history" className="text-meta font-medium text-ink hover:underline">
                  All history
                </Link>
              )
            }
          >
            Recent activity
          </SectionTitle>
          {recent.items.length === 0 ? (
            <Empty icon="activity" title="No activity yet" actions={can(me, "activities.create") && <LogActivityButton
                  label="Log activity"
                  org={me.org}
                  now={new Date().toISOString()}
                  people={people}
                  companies={companies.items.map((c) => ({ id: c.id, name: c.name }))}
                />}>
              Whatever your team logs against a customer shows up here.
            </Empty>
          ) : (
            <ul className="divide-y divide-rule">
              {recent.items.map((a) => {
                const kind = kindOf(a.kind);
                const customer = customerOf(a);
                return (
                  <li key={a.id} className="py-3">
                    <p className="text-meta text-ink-3">
                      <span className="inline-flex items-center gap-1 align-[-2px] font-semibold text-ink-2">
                        <Icon name={kind.icon} className="size-3.5" />
                        {kind.label}
                      </span>{" "}
                      · {fmt.whenLabel(a.at, today)} · {a.owner.name}
                    </p>
                    <p className="mt-0.5">
                      {customer.href ? (
                        <Link href={customer.href} className="font-medium text-ink hover:underline">
                          {customer.name}
                        </Link>
                      ) : null}
                      <span className="text-ink-2">
                        {customer.href ? " — " : ""}
                        {a.subject}
                      </span>
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </Sheet>
      </div>
    </>
  );
}
