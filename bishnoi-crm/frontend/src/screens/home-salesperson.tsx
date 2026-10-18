import Link from "next/link";
import { Suspense } from "react";
import { FollowUpItem } from "../components/follow-up-item";
import { NewCustomerButton } from "../components/crm/new-customer";
import { Icon } from "@/src/platform/ui/icons";
import { QuoteStateMark } from "@/src/platform/ui/marks";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { Bars } from "@/src/platform/ui/bars";
import { Later } from "@/src/platform/ui/later";
import { Chart, ListRows } from "@/src/platform/ui/skeleton";
import { can } from "@/src/platform/lib/access";
import { AttentionPanel } from "../components/attention-panel";
import { getCompanyMe, query } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { ActivityItem, ActivitySummary, Assignable, CompanyRow, DealList, DealSummary, ModuleRetention, Paged, Quote, SalesResults } from "@/src/platform/lib/types";
import { CardLink, Change, DueList, Insight, LIST_ROWS, Overview, OverviewLoading, PartTitle, ShareRing, quotedInsight, type Stat } from "../components/dashboard/parts";
import { PanelTabs } from "@/src/platform/ui/panel-tabs";
import { Donut, SERIES } from "../components/deals/donut";
import { StageTag } from "../components/deals/words";
import { paceFigure } from "../components/kpis/performance";
import { MonthBars } from "../components/month-bars";
import { customerOf, dayOf, followUpRow } from "../components/crm/follow-up-rows";
import { LogActivityButton } from "../components/crm/log-activity-button";
import { kindOf } from "../components/crm/words";

type RepData = {
  counts?: ActivitySummary | null;
  mine?: Paged<ActivityItem> | null;
  recent?: Paged<ActivityItem> | null;
  myQuotes?: Paged<Quote> | null;
  toApprove?: Paged<Quote> | null;
  people?: Assignable[] | null;
  companies?: { items: Pick<CompanyRow, "id" | "name">[]; total: number } | null;
  trend?: { thisMonth: string; points: { month: string; quotedCentavos: number; wonCentavos: number; newCustomers: number }[] } | null;
  results?: SalesResults | null;
  pipeline?: DealSummary | null;
  deals?: DealList | null;
  retention?: ModuleRetention | null;
};

const OVERVIEW = [
  { icon: "goals", label: "Revenue won" },
  { icon: "deals", label: "Open pipeline" },
  { icon: "quotes", label: "Quoted this month" },
  { icon: "retention", label: "Customers kept" },
] as const;

/**
 * A salesperson's dashboard. How the month stands first (four figures, each
 * against a target or last month, so each says whether it's good); then the
 * day's work beside how quoting has gone; then their customers (kept, how the
 * rest stand, what was done lately); then the deals and quotes in hand.
 */
export async function SalespersonHome() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const seesActivities = can(me, "activities.view");
  const seesQuotes = can(me, "quotes.view");
  const approver = can(me, "quotes.approve");
  const none: Paged<never> = { items: [], total: 0 };
  const logs = can(me, "activities.create");
  const seesDeals = can(me, "deals.view");
  const seesCustomers = can(me, "customers.view");
  // Home's one request, asked for and not waited on: the greeting and every card's
  // frame are drawn now and fill in as it lands. The customers are for the "log a call" picker, so only their names.
  const answer = query<RepData>(
    `query RepHome($activities: Boolean!, $quotes: Boolean!, $approver: Boolean!, $logs: Boolean!, $customers: Boolean!, $deals: Boolean!, $retention: Boolean!) {
      counts: activitySummary(owner: "me") @include(if: $activities)
      mine: activities(owner: "me", state: "open", limit: 100) @include(if: $activities)
      recent: activities(state: "done", limit: 5) @include(if: $activities)
      myQuotes: quotes(owner: "me", limit: 6) @include(if: $quotes)
      toApprove: quotes(task: "approvals", limit: 1) @include(if: $approver)
      people @include(if: $logs) { id name isMe team { id name } }
      companies(limit: 200) @include(if: $customers) { total items { id name } }
      trend: salesTrend(months: 12, view: "mine") @include(if: $deals)
      results: salesResults(view: "mine") @include(if: $deals)
      pipeline: dealsSummary(state: "open", owner: "me") @include(if: $deals)
      deals(owner: "me", state: "open", sort: "close", limit: 5) @include(if: $deals)
      retention(view: "mine") @include(if: $retention)
    }`,
    { activities: seesActivities, quotes: seesQuotes, approver, logs, customers: logs && seesCustomers, deals: seesDeals, retention: seesCustomers },
  );
  return (
    <>
      <PageHeader
        title="Dashboard"
        actions={
          <>
            {can(me, "customers.create") && <NewCustomerButton variant="default" />}
            {logs && (
              <Later data={answer} fallback={null}>
                {({ data }) => (
                  <LogActivityButton
                    variant="primary"
                    org={me.org}
                    now={new Date().toISOString()}
                    people={data.people ?? []}
                    companies={(data.companies ?? none).items.map((c) => ({ id: c.id, name: c.name }))}
                  />
                )}
              </Later>
            )}
          </>
        }
      >
        {fmt.greeting()}, {me.user.fullName.split(" ")[0]}. {me.role?.name}
        {me.team ? ` · ${me.team.name}` : ""} · {fmt.monthLabel(dayOf(new Date().toISOString(), me.org.timezone).slice(0, 7))}
      </PageHeader>
      <Suspense fallback={null}>
        <AttentionPanel skip={seesDeals ? ["target"] : []} />
      </Suspense>
      <Suspense fallback={<RepLoading activities={seesActivities} deals={seesDeals} quotes={seesQuotes} customers={seesCustomers} />}>
        <RepCards me={me} answer={answer} />
      </Suspense>
    </>
  );
}

/** The dashboard as it waits: each card already its own title, the figures to come. */
function RepLoading({ activities, deals, quotes, customers }: { activities: boolean; deals: boolean; quotes: boolean; customers: boolean }) {
  const rows = (n: number, columns = 2) => (
    <div className="-mx-5">
      <ListRows rows={n} columns={columns} />
    </div>
  );
  return (
    <>
      <OverviewLoading stats={[...OVERVIEW]} />
      <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        {deals && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="trend">Quoted, last 12 months</SectionTitle>
            <div className="mt-4">
              <Chart />
            </div>
          </Sheet>
        )}
        {activities && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="followUps">To do</SectionTitle>
            {rows(4)}
          </Sheet>
        )}
      </div>
      {customers && (
        <Sheet className="mb-5 px-5 py-4">
          <SectionTitle icon="customers">My customers</SectionTitle>
          {rows(4, 3)}
        </Sheet>
      )}
      <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
        {deals && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="deals">Pipeline by stage</SectionTitle>
            <div className="mt-4">
              <Chart bars={6} />
            </div>
          </Sheet>
        )}
        {deals && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="deals">Deals closing soon</SectionTitle>
            {rows(3)}
          </Sheet>
        )}
        {quotes && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="quotes">My quotes</SectionTitle>
            {rows(3)}
          </Sheet>
        )}
      </div>
    </>
  );
}

type RepAnswer = Awaited<ReturnType<typeof query<RepData>>>;

async function RepCards({ me, answer }: { me: Awaited<ReturnType<typeof getCompanyMe>>; answer: Promise<RepAnswer> }) {
  const fmt = makeFormat(me.org);
  const seesActivities = can(me, "activities.view");
  const seesQuotes = can(me, "quotes.view");
  const approver = can(me, "quotes.approve");
  const none: Paged<never> = { items: [], total: 0 };
  const seesDeals = can(me, "deals.view");
  const { data } = await answer;
  const counts = data.counts ?? { overdue: 0, today: 0, upcoming: 0, open: 0 };
  const mine = data.mine ?? none;
  const recent = data.recent ?? none;
  const myQuotes = data.myQuotes ?? none;
  const toApprove = data.toApprove ?? none;
  const people = data.people ?? [];
  const companies = data.companies ?? none;
  const today = dayOf(new Date().toISOString(), me.org.timezone);
  const points = data.trend?.points ?? [];
  const [lastMonth, thisMonth] = points.slice(-2);
  const pipe = data.pipeline;
  const results = data.results;
  const totals = results?.totals;
  const kept = data.retention?.summary;
  const keptPct = kept?.rate !== null && kept?.rate !== undefined ? Math.round(kept.rate * 100) : null;
  const revenue = totals
    ? paceFigure({ value: fmt.peso(totals.wonCentavos), label: "Revenue won", actual: totals.wonCentavos, target: totals.targetCentavos, start: results!.start, end: results!.end, today, show: fmt.peso, href: "/performance" })
    : null;
  const closing = data.deals?.items ?? [];
  // Due now: overdue first, then today. Then the next few ahead, so a quiet day
  // still shows what's planned; the rest waits in Activities.
  const rows = mine.items.map((a) => followUpRow(a, today, me.org.timezone));
  const due = rows.filter((f) => f.bucket === "overdue" || f.bucket === "today");
  const ahead = rows.filter((f) => f.bucket === "upcoming").sort((a, b) => a.dueOn.localeCompare(b.dueOn));
  const needsHand = myQuotes.items.filter((q) => q.state !== "ready");
  const insight = quotedInsight(points, fmt);

  const stats: Stat[] = [
    { icon: "goals", label: "Revenue won", href: "/performance", value: revenue?.value ?? "—", pill: revenue?.pill, note: revenue?.note ?? "Deals aren't open to your role" },
    {
      icon: "deals",
      label: "Open pipeline",
      href: "/deals?who=me",
      value: pipe ? fmt.peso(pipe.valueCentavos) : "—",
      note: pipe ? (pipe.count ? `${fmt.plural(pipe.count, "open deal")} · ${fmt.peso(pipe.weightedCentavos)} weighted` : "No open deals yet") : "Deals aren't open to your role",
    },
    {
      icon: "quotes",
      label: "Quoted this month",
      href: "/quotes?owner=me",
      value: thisMonth ? fmt.peso(thisMonth.quotedCentavos) : "—",
      note: thisMonth ? <Change now={thisMonth.quotedCentavos} before={lastMonth?.quotedCentavos} /> : "Sales reports aren't open to your role",
    },
    {
      icon: "retention",
      label: "Customers kept",
      href: "/retention",
      value: keptPct === null ? "—" : `${keptPct}%`,
      note: kept ? (keptPct === null ? "None to compare yet" : `${kept.retained} of ${kept.base} quoted again · ${kept.atRisk} at risk`) : "Retention isn't open to your role",
    },
  ];

  return (
    <>
      <Overview action={<CardLink href="/performance">View performance</CardLink>} stats={stats} />

      {/* The day's work beside how quoting has gone. */}
      <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        {seesDeals && (
          <Sheet className="flex flex-col px-5 py-4">
            <SectionTitle icon="trend" action={<CardLink href="/quotes?owner=me">All my quotes</CardLink>}>
              Quoted, last 12 months
            </SectionTitle>
            <div className="mt-4 flex flex-1 flex-col">
              {points.some((p) => p.quotedCentavos > 0) ? (
                <MonthBars
                  fill
                  label="Quoted"
                  current={data.trend?.thisMonth ?? ""}
                  points={points.map((p) => ({ month: p.month, value: p.quotedCentavos, text: fmt.pesoCompact(p.quotedCentavos), monthLabel: fmt.monthLabel(p.month).slice(0, 3) }))}
                />
              ) : (
                <Empty compact icon="quotes" title="No quotes yet">
                  What you quote each month shows here.
                </Empty>
              )}
            </div>
            {insight && <Insight>{insight}</Insight>}
          </Sheet>
        )}
        {seesActivities && (
          <Sheet className="flex flex-col px-5 py-4">
            <SectionTitle icon="followUps" action={<CardLink href="/activities">All to do</CardLink>}>
              To do
            </SectionTitle>
            <p className="mt-1 text-meta text-ink-3">
              <span className={counts.overdue ? "font-semibold text-danger" : ""}>{counts.overdue} overdue</span> · {counts.today} today · {counts.upcoming} coming up
            </p>
            {due.length + ahead.length === 0 ? (
              <div className="flex flex-1 flex-col justify-center">
                <Empty
                  compact
                  icon="followUps"
                  title="Nothing planned"
                  actions={
                    can(me, "activities.create") && (
                      <LogActivityButton label="Plan a follow-up" org={me.org} now={new Date().toISOString()} people={people} companies={companies.items.map((c) => ({ id: c.id, name: c.name }))} />
                    )
                  }
                >
                  Meetings and tasks you plan show up here on the day.
                </Empty>
              </div>
            ) : (
              <div className="mt-3">
                <PanelTabs
                  label="To do"
                  tabs={[
                    { value: "due", label: "Due now", count: due.length, content: <DueList rows={due} today={today} org={me.org} empty="Nothing due today." more={due.length > LIST_ROWS ? "/activities" : undefined} /> },
                    { value: "ahead", label: "Coming up", count: ahead.length, content: <DueList rows={ahead} today={today} org={me.org} empty="Nothing planned ahead." more={ahead.length > LIST_ROWS ? "/activities" : undefined} /> },
                  ]}
                />
              </div>
            )}
          </Sheet>
        )}
      </div>

      {/* Their customers: how many were kept, how the rest stand, what was done lately. */}
      {kept && (
        <Sheet className="mb-5 px-5 py-4">
          <SectionTitle icon="customers" action={<CardLink href="/retention">View retention</CardLink>}>
            My customers
          </SectionTitle>
          <div className="mt-4 grid items-start gap-x-8 gap-y-6 md:grid-cols-[auto_minmax(0,1fr)] xl:grid-cols-[auto_minmax(0,1fr)_minmax(0,1.3fr)]">
            <ShareRing pct={keptPct} label="Kept" count={kept.customers} sub={kept.base ? `${kept.retained} of ${kept.base} customers` : `${kept.new} new`} />
            <div className="min-w-0">
              <PartTitle>Customer health</PartTitle>
              <Bars
                rows={[
                  { label: "Healthy", value: kept.healthy, href: "/retention" },
                  { label: "At risk", value: kept.atRisk, href: "/retention", flag: true },
                  { label: "Lost", value: kept.lostNow, href: "/retention", flag: true },
                  { label: "No quotes yet", value: kept.noQuotes, href: "/retention" },
                  { label: "New this window", value: kept.new, href: "/retention" },
                ]}
              />
            </div>
            <div className="min-w-0 md:col-span-2 xl:col-span-1">
              <PartTitle action={seesActivities && <CardLink href="/activities?view=history">All history</CardLink>}>Recent activity</PartTitle>
              {recent.items.length === 0 ? (
                <p className="mt-2 text-meta text-ink-3">Whatever your team logs against a customer shows up here.</p>
              ) : (
                <ul className="divide-y divide-rule">
                  {recent.items.slice(0, 4).map((a) => {
                    const kind = kindOf(a.kind);
                    const customer = customerOf(a);
                    return (
                      <li key={a.id} className="flex items-start gap-3 py-2.5">
                        <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-mint text-sage-deep" aria-hidden>
                          <Icon name={kind.icon} className="size-4" />
                        </span>
                        <span className="min-w-0 flex-1">
                          {customer.href ? (
                            <Link href={customer.href} className="block truncate text-sm font-medium text-ink hover:underline">
                              {customer.name}
                            </Link>
                          ) : (
                            <span className="block truncate text-sm font-medium text-ink">{a.subject}</span>
                          )}
                          <span className="block truncate text-meta text-ink-3">
                            {kind.label}: {a.subject}
                          </span>
                        </span>
                        <span className="shrink-0 text-meta text-ink-3">{fmt.whenLabel(a.at, today)}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
        </Sheet>
      )}

      {/* What's in hand: the pipeline, the deals closing soonest, quotes that need a hand. */}
      <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
        {seesDeals && (
          <Sheet className="flex flex-col px-5 py-4">
            <SectionTitle icon="deals" action={<CardLink href="/deals?who=me">View deals</CardLink>}>
              Pipeline by stage
            </SectionTitle>
            {pipe && pipe.count ? (
              <div className="mt-4">
                <Donut
                  title="Open deals by stage"
                  totalLabel="Deals"
                  slices={pipe.byStage.map((st, i) => ({ label: st.name, value: st.count, color: SERIES[i % SERIES.length], note: fmt.peso(st.valueCentavos) }))}
                />
                <p className="mt-4 border-t border-rule pt-3 text-meta text-ink-3">
                  <span className="font-semibold text-ink tabular-nums">{fmt.peso(pipe.valueCentavos)}</span> open · {fmt.peso(pipe.weightedCentavos)} likely, weighted by
                  each stage&apos;s chance
                </p>
              </div>
            ) : (
              <div className="flex flex-1 flex-col justify-center">
                <Empty compact icon="deals" art="steps" title="No open deals">
                  A deal on a customer shows here by its stage until it&apos;s won or lost.
                </Empty>
              </div>
            )}
          </Sheet>
        )}
        {seesDeals && (
          <Sheet className="flex flex-col px-5 py-4">
            <SectionTitle icon="deals" action={<CardLink href="/deals?who=me">All my deals</CardLink>}>
              Deals closing soon
            </SectionTitle>
            {closing.length === 0 ? (
              <div className="flex flex-1 flex-col justify-center">
                <Empty compact icon="deals" art="steps" title="No open deals">
                  A deal on a customer shows here until it&apos;s won or lost, soonest to close first.
                </Empty>
              </div>
            ) : (
              <ul className="mt-1 divide-y divide-rule">
                {closing.map((d) => (
                  <li key={d.id} className="flex items-center justify-between gap-3 py-2.5">
                    <span className="min-w-0">
                      <Link href={`/deals/${d.id}`} className="block truncate font-medium text-ink hover:underline">
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
          <Sheet className="flex flex-col px-5 py-4">
            <SectionTitle icon="quotes" action={<CardLink href="/quotes?owner=me">All my quotes</CardLink>}>
              My quotes
            </SectionTitle>
            {approver && toApprove.total > 0 && (
              <Link href="/quotes?task=approvals" className="mt-2 flex items-center justify-between rounded-lg bg-hema-tint px-3 py-2 text-sm font-medium text-ink hover:underline">
                {toApprove.total} {toApprove.total === 1 ? "quote is" : "quotes are"} waiting for your approval
                <span aria-hidden>→</span>
              </Link>
            )}
            {needsHand.length === 0 ? (
              <div className="flex flex-1 flex-col justify-center">
                <Empty compact icon="quotes" title={myQuotes.total ? "All quotes ready" : "No quotes yet"}>
                  {myQuotes.total ? "None waiting for approval or rejected." : "Make one from a customer's page, or with New quote."}
                </Empty>
              </div>
            ) : (
              <ul className="mt-1 divide-y divide-rule">
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
    </>
  );
}
