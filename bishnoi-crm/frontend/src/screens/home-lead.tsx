import Link from "next/link";
import { Suspense } from "react";
import { FollowUpItem } from "../components/follow-up-item";
import { NewCustomerButton } from "../components/crm/new-customer";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { Later } from "@/src/platform/ui/later";
import { Chart, ListRows } from "@/src/platform/ui/skeleton";
import { can } from "@/src/platform/lib/access";
import { AttentionPanel } from "../components/attention-panel";
import { query } from "@/src/platform/lib/api";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { ActivityItem, Assignable, CompanyRow, DealSummary, Me, ModuleRetention, Org, Paged, PeopleInsights, PersonInsight, Quote, SalesResults } from "@/src/platform/lib/types";
import { CardLink, Change, DueList, Insight, LIST_ROWS, Overview, OverviewLoading, quotedInsight, type Stat } from "../components/dashboard/parts";
import { PanelTabs } from "@/src/platform/ui/panel-tabs";
import { Donut, SERIES } from "../components/deals/donut";
import { paceFigure } from "../components/kpis/performance";
import { MonthBars } from "../components/month-bars";
import { customerOf, dayOf, followUpRow } from "../components/crm/follow-up-rows";
import { LogActivityButton } from "../components/crm/log-activity-button";
import { KINDS, kindOf } from "../components/crm/words";

type LeadData = {
  insights: PeopleInsights | null;
  trend?: { thisMonth: string; points: { month: string; quotedCentavos: number }[] } | null;
  pipeline?: DealSummary | null;
  retention?: ModuleRetention | null;
  teamDue: Paged<ActivityItem> | null;
  teamDone: Paged<ActivityItem> | null;
  toApprove?: Paged<Quote> | null;
  people: Assignable[] | null;
  companies?: { items: Pick<CompanyRow, "id" | "name">[]; total: number } | null;
  results?: SalesResults | null;
};

/** What each person did this week, in words: "3 calls · 1 meeting". */
function didWords(p: PersonInsight): string {
  const parts = KINDS.filter((k) => p.doneByKind[k.kind]).map((k) => {
    const n = p.doneByKind[k.kind]!;
    return `${n} ${n === 1 ? k.label.toLowerCase() : `${k.label.toLowerCase()}s`}`;
  });
  return parts.join(" · ") || "Nothing logged";
}

function TeamTable({ people, fmt, today }: { people: PersonInsight[]; fmt: Format; today: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[52rem] text-sm">
        <thead>
          <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
            <th scope="col" className="py-2 pr-3 font-semibold">Person</th>
            <th scope="col" className="px-3 py-2 font-semibold">To do</th>
            <th scope="col" className="px-3 py-2 font-semibold">Completed this week</th>
            <th scope="col" className="px-3 py-2 text-right font-semibold">Customers</th>
            <th scope="col" className="px-3 py-2 text-right font-semibold">Quoted this month</th>
            <th scope="col" className="py-2 pl-3 text-right font-semibold">Last active</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {people.map((p) => (
            <tr key={p.id} className={p.overdue ? "bg-danger-tint/40" : ""}>
              <th scope="row" className="py-2.5 pr-3 text-left font-medium">
                <Link href={`/activities?who=team&person=${p.id}`} className="text-ink hover:underline">
                  {p.isMe ? "You" : p.name}
                </Link>
                <span className="block text-meta font-normal text-ink-3">{p.role}</span>
              </th>
              <td className="px-3 py-2.5">
                {p.overdue > 0 && <span className="font-semibold text-danger">{p.overdue} overdue</span>}
                {p.overdue > 0 && (p.dueToday > 0 || p.upcoming > 0) && <span className="text-ink-3"> · </span>}
                {p.dueToday > 0 && <span>{p.dueToday} today</span>}
                {p.dueToday > 0 && p.upcoming > 0 && <span className="text-ink-3"> · </span>}
                {p.upcoming > 0 && <span className="text-ink-2">{p.upcoming} coming up</span>}
                {!p.overdue && !p.dueToday && !p.upcoming && <span className="text-ink-3">None planned</span>}
              </td>
              <td className={`px-3 py-2.5 ${p.doneThisWeek ? "" : "text-ink-3"}`}>{didWords(p)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">
                {p.customers}
                {p.newCustomersThisMonth > 0 && <span className="block text-meta text-ink-3">+{p.newCustomersThisMonth} this month</span>}
              </td>
              <td className="px-3 py-2.5 text-right tabular-nums">
                {p.quotesThisMonth ? fmt.peso(p.quotedThisMonthCentavos) : "—"}
                <span className="block text-meta text-ink-3">
                  {[
                    p.quotesThisMonth && `${p.quotesThisMonth} ${p.quotesThisMonth === 1 ? "quote" : "quotes"}`,
                    p.quotesWaiting && `${p.quotesWaiting} waiting`,
                    p.quotesRejectedThisMonth && `${p.quotesRejectedThisMonth} rejected`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </td>
              <td className="py-2.5 pl-3 text-right text-meta text-ink-2">{p.lastActivityAt ? fmt.whenLabel(p.lastActivityAt, today) : "Never"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// The team table shows the ones furthest behind; the rest are a click away.
const TEAM_ROWS = 10;

const OVERVIEW = [
  { icon: "goals", label: "Team revenue won" },
  { icon: "deals", label: "Team pipeline" },
  { icon: "quotes", label: "Quoted this month" },
  { icon: "retention", label: "Customers kept" },
] as const;

/**
 * A team lead's dashboard: the team's month in four figures, each against a
 * target or last month; what's due across the team beside how quoting has
 * gone; each person, furthest behind first; then what waits on them, the
 * pipeline and what the team did.
 */
export function LeadHome({ me }: { me: Me & { org: Org } }) {
  const fmt = makeFormat(me.org);
  const none: Paged<never> = { items: [], total: 0 };
  const approver = can(me, "quotes.approve");
  const sales = can(me, "deals.view") && can(me, "reports.view");
  // Home's one request, asked for and not waited on: the greeting and every card's
  // frame are drawn now and fill in as it lands. The customers are for the "log a call" picker, so only their names.
  const answer = query<LeadData>(
    `query LeadHome($approver: Boolean!, $customers: Boolean!, $sales: Boolean!, $deals: Boolean!) {
      insights: peopleInsights
      teamDue: activities(state: "open", limit: 200)
      teamDone: activities(state: "done", limit: 6)
      toApprove: quotes(task: "approvals", limit: 5) @include(if: $approver)
      results: salesResults(view: "team") @include(if: $sales)
      trend: salesTrend(months: 12, view: "team") @include(if: $sales)
      pipeline: dealsSummary(state: "open") @include(if: $deals)
      retention(view: "team") @include(if: $customers)
      people { id name isMe team { id name } }
      companies(limit: 200) @include(if: $customers) { total items { id name } }
    }`,
    { approver, customers: can(me, "customers.view"), sales, deals: can(me, "deals.view") },
  );

  return (
    <>
      <PageHeader
        title="Dashboard"
        actions={
          <>
            {can(me, "customers.create") && <NewCustomerButton variant="default" />}
            {can(me, "activities.create") && (
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
        {fmt.greeting()}, {me.user.fullName.split(" ")[0]}. You lead {me.team?.name ?? "your team"}
        <Later data={answer} fallback=".">
          {({ data }) => {
            const others = (data.insights?.people ?? []).filter((p) => !p.isMe);
            return `: ${others.length} ${others.length === 1 ? "person" : "people"}.`;
          }}
        </Later>
      </PageHeader>
      <Suspense fallback={null}>
        <AttentionPanel />
      </Suspense>
      <Suspense fallback={<LeadLoading approver={approver} sales={sales} />}>
        <LeadCards me={me} answer={answer} />
      </Suspense>
    </>
  );
}

/** The dashboard as it waits: each card already its own title, the figures to come. */
function LeadLoading({ approver, sales }: { approver: boolean; sales: boolean }) {
  const rows = (n: number, columns = 3) => (
    <div className="-mx-5">
      <ListRows rows={n} columns={columns} />
    </div>
  );
  return (
    <>
      <OverviewLoading title="Team overview" stats={[...OVERVIEW]} />
      <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        {sales && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="trend">Team quoted, last 12 months</SectionTitle>
            <div className="mt-4">
              <Chart />
            </div>
          </Sheet>
        )}
        <Sheet className="px-5 py-4">
          <SectionTitle icon="followUps">Due in the team</SectionTitle>
          {rows(4, 2)}
        </Sheet>
      </div>
      <Sheet className="mb-5 px-5 py-4">
        <SectionTitle icon="teams">Team</SectionTitle>
        {rows(5)}
      </Sheet>
      <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
        {approver && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="quotes">Waiting for your approval</SectionTitle>
            {rows(3, 2)}
          </Sheet>
        )}
        <Sheet className="px-5 py-4">
          <SectionTitle icon="deals">Team pipeline by stage</SectionTitle>
          <div className="mt-4">
            <Chart bars={6} />
          </div>
        </Sheet>
        <Sheet className="px-5 py-4">
          <SectionTitle icon="activity">Team activity</SectionTitle>
          {rows(4, 2)}
        </Sheet>
      </div>
    </>
  );
}

async function LeadCards({ me, answer }: { me: Me & { org: Org }; answer: Promise<{ data: LeadData }> }) {
  const fmt = makeFormat(me.org);
  const none: Paged<never> = { items: [], total: 0 };
  const approver = can(me, "quotes.approve");
  const { data } = await answer;
  if (!data.insights) throw new Error("Home couldn't read how your team is doing.");
  const insights = data.insights;
  const teamDue = data.teamDue ?? none;
  const teamDone = data.teamDone ?? none;
  const toApprove = data.toApprove ?? none;
  const people = data.people ?? [];
  const companies = data.companies ?? none;
  const today = dayOf(new Date().toISOString(), me.org.timezone);
  const t = insights.totals;
  // Due now across the team, overdue first: each with whose it is. Then the next few ahead.
  const rows = teamDue.items.map((a) => followUpRow(a, today, me.org.timezone, { place: a.owner.id === me.user.id ? "You" : a.owner.name }));
  const due = rows
    .filter((f) => f.bucket === "overdue" || f.bucket === "today")
    .sort((a, b) => (a.bucket === b.bucket ? a.dueOn.localeCompare(b.dueOn) : a.bucket === "overdue" ? -1 : 1));
  const upcoming = rows.filter((f) => f.bucket === "upcoming").sort((a, b) => a.dueOn.localeCompare(b.dueOn));
  const ahead = upcoming;
  const aheadCount = upcoming.length;
  const r = data.results;
  const points = data.trend?.points ?? [];
  const [lastMonth, thisMonth] = points.slice(-2);
  const pipe = data.pipeline;
  const kept = data.retention?.summary;
  const keptPct = kept?.rate !== null && kept?.rate !== undefined ? Math.round(kept.rate * 100) : null;
  const revenue = r
    ? paceFigure({ value: fmt.peso(r.totals.wonCentavos), label: "Team revenue won", actual: r.totals.wonCentavos, target: r.totals.targetCentavos, start: r.start, end: r.end, today, show: fmt.peso, href: "/performance", noTarget: "No revenue target set for the team" })
    : null;
  const insight = quotedInsight(points, fmt, "The team's");

  const stats: Stat[] = [
    { icon: "goals", label: "Team revenue won", href: "/performance", value: revenue?.value ?? "—", pill: revenue?.pill, note: revenue?.note ?? "Sales reports aren't open to your role" },
    {
      icon: "deals",
      label: "Team pipeline",
      href: "/deals",
      value: pipe ? fmt.peso(pipe.valueCentavos) : "—",
      note: pipe ? (pipe.count ? `${fmt.plural(pipe.count, "open deal")} · ${fmt.peso(pipe.weightedCentavos)} weighted` : "No open deals yet") : "Deals aren't open to your role",
    },
    {
      icon: "quotes",
      label: "Quoted this month",
      href: "/quotes",
      value: fmt.peso(t.quotedThisMonthCentavos),
      note: thisMonth ? <Change now={thisMonth.quotedCentavos} before={lastMonth?.quotedCentavos} /> : fmt.plural(t.quotesThisMonth, "quote"),
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
      <Overview title="Team overview" action={can(me, "goals.view") && <CardLink href="/performance">View performance</CardLink>} stats={stats} />

      {/* What's due across the team beside how the team has quoted. */}
      <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        {r && (
          <Sheet className="flex flex-col px-5 py-4">
            <SectionTitle icon="trend" action={<CardLink href="/quotes">All quotes</CardLink>}>
              Team quoted, last 12 months
            </SectionTitle>
            <div className="mt-4 flex flex-1 flex-col">
              {points.some((p) => p.quotedCentavos > 0) ? (
                <MonthBars
                  fill
                  label="Quoted by the team"
                  current={data.trend?.thisMonth ?? ""}
                  points={points.map((p) => ({ month: p.month, value: p.quotedCentavos, text: fmt.pesoCompact(p.quotedCentavos), monthLabel: fmt.monthLabel(p.month).slice(0, 3) }))}
                />
              ) : (
                <Empty compact icon="quotes" title="No quotes yet">
                  What the team quotes each month shows here.
                </Empty>
              )}
            </div>
            {insight && <Insight>{insight}</Insight>}
          </Sheet>
        )}
        <Sheet className="flex flex-col px-5 py-4">
          <SectionTitle icon="followUps" action={<CardLink href="/activities?who=team">All team to do</CardLink>}>
            Due in the team
          </SectionTitle>
          <p className="mt-1 text-meta text-ink-3">
            <span className={t.overdue ? "font-semibold text-danger" : ""}>{t.overdue} overdue</span> · {t.dueToday} today · {t.doneThisWeek} completed this week by{" "}
            {t.activeThisWeek} of {t.people}
          </p>
          {due.length === 0 && aheadCount === 0 ? (
            <div className="flex flex-1 flex-col justify-center">
              <Empty compact icon="followUps" title="Nothing due in the team">
                Overdue and today&apos;s meetings and tasks across the team show up here.
              </Empty>
            </div>
          ) : (
            <div className="mt-3">
              <PanelTabs
                label="Due in the team"
                tabs={[
                  { value: "due", label: "Due now", count: due.length, content: <DueList rows={due} today={today} org={me.org} empty="Nothing due today in the team." more={due.length > LIST_ROWS ? "/activities?who=team" : undefined} /> },
                  { value: "ahead", label: "Coming up", count: aheadCount, content: <DueList rows={ahead} today={today} org={me.org} empty="Nothing planned ahead in the team." more={aheadCount > LIST_ROWS ? "/activities?who=team" : undefined} /> },
                ]}
              />
            </div>
          )}
        </Sheet>
      </div>

      {/* Each person, furthest behind first. */}
      <Sheet className="mb-5 px-5 py-4">
        <SectionTitle icon="teams" action={insights.people.length > TEAM_ROWS && <CardLink href="/activities?who=team">All {insights.people.length} people</CardLink>}>
          Team
        </SectionTitle>
        <p className="mt-1 mb-2 text-meta text-ink-3">
          {insights.people.length > TEAM_ROWS ? `The ${TEAM_ROWS} furthest behind of ${insights.people.length}.` : "Sorted by those furthest behind."} Select a name to view their to do.
        </p>
        <TeamTable people={insights.people.slice(0, TEAM_ROWS)} fmt={fmt} today={today} />
      </Sheet>

      {/* What waits on the lead, where the pipeline sits, what the team did. */}
      <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
        {approver && (
          <Sheet className="flex flex-col px-5 py-4">
            <SectionTitle icon="quotes" action={toApprove.total > 0 && <CardLink href="/quotes?task=approvals">All {toApprove.total} waiting</CardLink>}>
              Waiting for your approval
            </SectionTitle>
            {toApprove.items.length === 0 ? (
              <div className="flex flex-1 flex-col justify-center">
                <Empty compact icon="approvals" title="Nothing waiting">
                  Quotes that need your approval show up here.
                </Empty>
              </div>
            ) : (
              <ul className="mt-1 divide-y divide-rule">
                {toApprove.items.map((q) => (
                  <li key={q.id} className="flex items-center justify-between gap-3 py-2.5">
                    <span className="min-w-0">
                      <Link href={`/quotes/${q.id}`} className="font-medium text-ink hover:underline">
                        {q.number}
                      </Link>
                      <span className="block truncate text-meta text-ink-3">
                        {q.customerName} · by {q.createdBy.name}
                      </span>
                    </span>
                    <span className="flex shrink-0 items-center gap-3">
                      <span className="text-sm tabular-nums">{fmt.peso(q.totalCentavos)}</span>
                      <Link href={`/quotes/${q.id}`} className="rounded-md border border-ink px-3 py-1 text-meta font-medium text-ink hover:bg-mint">
                        Review
                      </Link>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Sheet>
        )}
        <Sheet className="flex flex-col px-5 py-4">
          <SectionTitle icon="deals" action={<CardLink href="/deals">View deals</CardLink>}>
            Team pipeline by stage
          </SectionTitle>
          {pipe && pipe.count ? (
            <div className="mt-4">
              <Donut
                title="The team's open deals by stage"
                totalLabel="Deals"
                slices={pipe.byStage.map((st, i) => ({ label: st.name, value: st.count, color: SERIES[i % SERIES.length], note: fmt.peso(st.valueCentavos) }))}
              />
              <p className="mt-4 border-t border-rule pt-3 text-meta text-ink-3">
                <span className="font-semibold text-ink tabular-nums">{fmt.peso(pipe.valueCentavos)}</span> open · {fmt.peso(pipe.weightedCentavos)} likely, weighted by each
                stage&apos;s chance
              </p>
            </div>
          ) : (
            <div className="flex flex-1 flex-col justify-center">
              <Empty compact icon="deals" art="steps" title="No open deals">
                The team&apos;s deals show here by stage until they&apos;re won or lost.
              </Empty>
            </div>
          )}
        </Sheet>
        <Sheet className="flex flex-col px-5 py-4">
          <SectionTitle icon="activity" action={<CardLink href="/activities?view=history&who=team">All team history</CardLink>}>
            Team activity
          </SectionTitle>
          {teamDone.items.length === 0 ? (
            <div className="flex flex-1 flex-col justify-center">
              <Empty
                compact
                icon="activity"
                title="No activity yet"
                actions={
                  can(me, "activities.create") && (
                    <LogActivityButton label="Log activity" org={me.org} now={new Date().toISOString()} people={people} companies={companies.items.map((c) => ({ id: c.id, name: c.name }))} />
                  )
                }
              >
                Calls, meetings, emails and notes your team logs show up here.
              </Empty>
            </div>
          ) : (
            <ul className="mt-1 divide-y divide-rule">
              {teamDone.items.map((a) => {
                const kind = kindOf(a.kind);
                const customer = customerOf(a);
                return (
                  <li key={a.id} className="flex items-start gap-3 py-2.5">
                    <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-mint text-sage-deep" aria-hidden>
                      <Icon name={kind.icon} className="size-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-ink">
                        {customer.href ? (
                          <Link href={customer.href} className="hover:underline">
                            {customer.name}
                          </Link>
                        ) : (
                          a.subject
                        )}
                      </span>
                      <span className="block truncate text-meta text-ink-3">
                        {a.owner.id === me.user.id ? "You" : a.owner.name} · {kind.label}: {a.subject}
                      </span>
                    </span>
                    <span className="shrink-0 text-meta text-ink-3">{fmt.whenLabel(a.doneAt ?? a.at, today)}</span>
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
