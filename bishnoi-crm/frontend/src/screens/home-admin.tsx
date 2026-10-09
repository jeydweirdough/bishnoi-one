import { ArrowDown, ArrowUp } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Avatar } from "@/src/platform/ui/avatar";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { can } from "@/src/platform/lib/access";
import { query } from "@/src/platform/lib/api";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { DealSummary, Me, ModuleRetention, Org, PeopleInsights, PersonInsight, SalesResults } from "@/src/platform/lib/types";
import { dayOf } from "../components/crm/follow-up-rows";
import { Donut, SERIES } from "../components/deals/donut";
import { Breakdown, FigureCard, type Figure } from "../components/deals/figure-card";
import { TargetProgress } from "../components/deals/target-progress";
import type { Performance } from "../components/field/types";
import { MonthBars } from "../components/month-bars";

type Params = Record<string, string | string[] | undefined>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

type Trend = { thisMonth: string; growth: number | null; points: { month: string; wonCentavos: number; wonCount: number; quotedCentavos: number; newCustomers: number }[] };

/** "+12%", "−8%", or nothing to compare. */
const change = (now: number, before: number) => (before ? `${now >= before ? "+" : "−"}${Math.abs(Math.round((100 * (now - before)) / before))}%` : null);

type Row = PersonInsight & { wonCentavos: number; wonCount: number };
const SORTS = {
  name: (a: Row, b: Row) => a.name.localeCompare(b.name),
  won: (a: Row, b: Row) => b.wonCentavos - a.wonCentavos,
  quoted: (a: Row, b: Row) => b.quotedThisMonthCentavos - a.quotedThisMonthCentavos,
  done: (a: Row, b: Row) => b.doneThisWeek - a.doneThisWeek,
  overdue: (a: Row, b: Row) => b.overdue - a.overdue,
};
type SortKey = keyof typeof SORTS;

/**
 * The Administrator's first page: how the company is selling. A row of four
 * figures; sales growth by month, with revenue against target, the pipeline,
 * and three smaller figures beside it; then how each person is doing, one role
 * at a time. Who signs in is under People and access.
 */
export async function AdminDashboard({ me, params = {} }: { me: Me & { org: Org }; params?: Params }) {
  const fmt = makeFormat(me.org);
  const reports = can(me, "reports.view");
  // Home's one request: each figure only when the person may see it.
  const { data } = await query<{ trend?: Trend | null; results?: SalesResults | null; deals?: DealSummary | null; retention?: ModuleRetention | null; field?: Performance | null; insights: PeopleInsights | null }>(
    `query AdminHome($reports: Boolean!, $results: Boolean!, $deals: Boolean!, $customers: Boolean!, $goals: Boolean!) {
      trend: salesTrend(months: 12) @include(if: $reports)
      results: salesResults(view: "team") @include(if: $results)
      deals: dealsSummary(state: "open") @include(if: $deals)
      retention(view: "team") @include(if: $customers)
      field: fieldPerformance @include(if: $goals)
      insights: peopleInsights
    }`,
    { reports, results: reports && can(me, "deals.view"), deals: can(me, "deals.view"), customers: can(me, "customers.view"), goals: can(me, "goals.view") },
  );
  const trend = data.trend ?? null;
  const results = data.results ?? null;
  const deals = data.deals ?? null;
  const retention = data.retention ?? null;
  const field = data.field ?? null;
  if (!data.insights) throw new Error("Home couldn't read how each person is doing.");
  const insights = data.insights;
  const today = dayOf(new Date().toISOString(), me.org.timezone);
  const points = trend?.points ?? [];
  const now = points[points.length - 1];
  const last = points[points.length - 2];
  const totals = results?.totals;

  const year = points.reduce((t, p) => t + p.wonCentavos, 0);
  const growth = trend?.growth ?? null;
  const busiest = deals ? [...deals.byStage].sort((x, y) => y.count - x.count)[0] : undefined;
  const quoted = now?.quotedCentavos ?? insights.totals.quotedThisMonthCentavos;
  const kept = retention?.summary.rate !== null && retention?.summary.rate !== undefined ? Math.round(retention.summary.rate * 100) : null;
  const winRate = totals?.winRate ?? null;
  const top: Figure[] = [
    {
      value: fmt.peso(deals?.weightedCentavos ?? 0),
      label: "Pipeline, weighted",
      note: deals ? `${fmt.peso(deals.valueCentavos)} in ${fmt.plural(deals.count, "open deal")}` : "Deals aren't open to your role",
      ring: deals && deals.valueCentavos ? Math.round((100 * deals.weightedCentavos) / deals.valueCentavos) : null,
      href: "/deals",
    },
    { value: fmt.peso(quoted), label: "Quoted this month", note: last ? `${change(now?.quotedCentavos ?? 0, last.quotedCentavos) ?? "—"} on last month` : `${insights.totals.quotesWaiting} waiting`, href: "/quotes" },
    {
      value: String(now?.newCustomers ?? insights.totals.newCustomersThisMonth),
      label: "New customers this month",
      note: last ? `Last month ${last.newCustomers}` : `${insights.totals.customers} in all`,
      href: "/companies",
    },
    {
      value: winRate === null ? "—" : `${winRate}%`,
      label: "Win rate this month",
      note: totals && totals.wonCount + totals.lostCount ? `${fmt.plural(totals.wonCount, "deal")} won, ${totals.lostCount} lost` : "No deals decided yet",
      ring: winRate,
      href: "/deals?view=closed",
    },
  ];
  const small: Figure[] = [
    {
      value: field ? fmt.peso(field.totals.amountCentavos) : "—",
      label: "Collected this month",
      note: field ? (field.totals.collectionVisits ? fmt.plural(field.totals.collectionVisits, "collection visit") : "No collection visits yet") : "Field work isn't open to your role",
      href: "/field",
    },
    {
      value: kept === null ? "—" : `${kept}%`,
      label: "Customers kept",
      note: retention ? (kept === null ? "Nothing to measure yet" : `${retention.summary.atRisk} at risk · ${retention.summary.lostNow} lost`) : "Retention isn't open to your role",
      ring: kept,
      href: "/retention",
      alert: (retention?.summary.atRisk ?? 0) > 0,
    },
  ];

  return (
    <>
      <PageHeader title="Dashboard">How the company is selling: revenue and its growth, the pipeline, and how each person is doing.</PageHeader>

      {/* As on the Deals page: the figure first, large; what it is; then how it compares. */}
      <div className="mb-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {top.map((f, n) => (
          <FigureCard key={f.label} figure={f} first={n === 0} />
        ))}
      </div>

      <div className="mb-3 grid gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Breakdown
          title="Sales growth"
          value={fmt.peso(year)}
          label={growth === null ? "won in the last 12 months" : `won in the last 12 months · ${growth >= 0 ? "+" : "−"}${Math.abs(growth)}% last full month on the one before`}
          empty={!trend ? "Sales reports aren't open to your role" : points.some((p) => p.wonCentavos > 0) ? undefined : "Nothing won yet"}
          emptyNote={trend ? "Revenue won each month shows here as deals are won." : "Ask an administrator for Reports → View."}
          art="steps"
          action={<SmallLink href="/deals?view=results">Results</SmallLink>}
        >
          <MonthBars
            label="Revenue won"
            current={trend?.thisMonth ?? ""}
            points={points.map((p) => ({ month: p.month, value: p.wonCentavos, text: fmt.pesoCompact(p.wonCentavos), monthLabel: fmt.monthLabel(p.month).slice(0, 3) }))}
          />
          <p className="mt-2 text-meta text-ink-3">Revenue won each month, the last 12. The light column is this month so far.</p>
        </Breakdown>

        <div className="grid gap-3 md:grid-cols-2">
          <Sheet className="px-5 py-4">
            <div className="flex items-start justify-between gap-3">
              <p className="text-caps text-ink-3 uppercase">Revenue against target</p>
              <SmallLink href="/performance/targets">Targets</SmallLink>
            </div>
            <div className="mt-2">
              {totals && results ? (
                <TargetProgress figures={totals} start={results.start} end={results.end} today={today} fmt={fmt} label={`Won in ${results.label}`} href="/performance/targets" withWinRate={false} />
              ) : (
                <Empty compact icon="goals" art="gauge" title="No sales results to show">
                  They fill in as deals are won.
                </Empty>
              )}
            </div>
          </Sheet>
          <Breakdown
            title="Pipeline by stage"
            value={busiest && deals?.count ? `${Math.round((100 * busiest.count) / deals.count)}%` : "—"}
            label={busiest ? `are at ${busiest.name}, the busiest stage` : ""}
            empty={deals && deals.count ? undefined : "No open deals yet"}
            art="steps"
            action={<SmallLink href="/deals">Deals</SmallLink>}
          >
            <Donut title="Open deals by stage" totalLabel="Deals" slices={(deals?.byStage ?? []).map((st, i) => ({ label: st.name, value: st.count, color: SERIES[i % SERIES.length], note: fmt.peso(st.valueCentavos) }))} />
          </Breakdown>
        </div>
      </div>

      <div className="mb-5 grid gap-3 sm:grid-cols-2">
        {small.map((f) => (
          <FigureCard key={f.label} figure={f} />
        ))}
      </div>

      <People fmt={fmt} insights={insights} results={results} params={params} />
    </>
  );
}

/** How each person is doing this month, one role at a time; or the teams. */
function People({ fmt, insights, results, params }: { fmt: Format; insights: PeopleInsights; results: SalesResults | null; params: Params }) {
  const won = new Map((results?.people ?? []).map((r) => [r.person.id, r]));
  const people: Row[] = insights.people
    .filter((p) => !p.isMe)
    .map((p) => ({ ...p, wonCentavos: won.get(p.id)?.wonCentavos ?? 0, wonCount: won.get(p.id)?.wonCount ?? 0 }));
  const count = new Map<string, number>();
  for (const p of people) count.set(p.role, (count.get(p.role) ?? 0) + 1);
  const roles = [...count.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const tab = one(params.tab) === "teams" ? "teams" : "people";
  const role = roles.some(([r]) => r === one(params.role)) ? one(params.role) : (roles[0]?.[0] ?? "");
  const sort = (Object.keys(SORTS) as SortKey[]).find((k) => k === one(params.sort)) ?? "won";
  const reverse = one(params.desc) === "1";
  const href = (c: Record<string, string>) => {
    const q = new URLSearchParams(
      Object.entries({ tab, role, sort, ...(reverse && { desc: "1" }), ...c }).filter(([k, v]) => v && !(k === "tab" && v === "people") && !(k === "sort" && v === "won")) as [string, string][],
    );
    return `/${q.size ? `?${q}` : ""}`;
  };
  const shown = people.filter((p) => p.role === role).sort((a, b) => (reverse ? -1 : 1) * SORTS[sort](a, b));
  const teams = new Map<string, { name: string; people: number; won: number; quoted: number; done: number; overdue: number }>();
  for (const p of people) {
    const name = p.team?.name ?? "No team";
    const t = teams.get(name) ?? { name, people: 0, won: 0, quoted: 0, done: 0, overdue: 0 };
    t.people += 1;
    t.won += p.wonCentavos;
    t.quoted += p.quotedThisMonthCentavos;
    t.done += p.doneThisWeek;
    t.overdue += p.overdue;
    teams.set(name, t);
  }
  const Head = ({ k, children, first }: { k: SortKey; children: ReactNode; first?: boolean }) => (
    <th scope="col" className={`py-2 font-medium ${first ? "px-5" : "px-3 text-right"}`} aria-sort={sort === k ? (reverse ? "descending" : "ascending") : undefined}>
      <Link href={href({ sort: k, desc: sort === k && !reverse ? "1" : "" })} className="inline-flex items-center gap-1 hover:text-ink">
        {children}
        {sort === k && (reverse ? <ArrowUp className="size-3" aria-hidden /> : <ArrowDown className="size-3" aria-hidden />)}
      </Link>
    </th>
  );

  return (
    <Sheet className="overflow-x-auto">
      <div className="flex flex-wrap items-center gap-3 border-b border-rule px-5 py-3">
        <h2 className="text-heading text-ink">This month, by person</h2>
        <span className="ml-auto">
          <ToggleLinks
            current={tab === "teams" ? "teams" : role}
            options={[
              ...roles.map(([name, n]) => ({ value: name, label: `${name} · ${n}`, href: href({ tab: "people", role: name, sort: "", desc: "" }) })),
              { value: "teams", label: "Teams", href: href({ tab: "teams" }) },
            ]}
          />
        </span>
      </div>
      {people.length === 0 ? (
        <div className="px-5 py-2">
          <Empty icon="people" title="Nobody else yet" actions={<LinkButton href="/admin/users/new" variant="primary">Add a person</LinkButton>}>
            Add the people who use the CRM, and give each a role.
          </Empty>
        </div>
      ) : tab === "teams" ? (
        <table className="w-full min-w-[40rem] text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-meta text-ink-3">
              <th scope="col" className="px-5 py-2 font-medium">Team</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Won this month</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Quoted this month</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Activities this week</th>
              <th scope="col" className="px-5 py-2 text-right font-medium">Overdue</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule tabular-nums">
            {[...teams.values()].sort((a, b) => b.won - a.won).map((t) => (
              <tr key={t.name}>
                <th scope="row" className="px-5 py-2.5 text-left font-medium">
                  {t.name}
                  <span className="block text-meta font-normal text-ink-3">{fmt.plural(t.people, "person", "people")}</span>
                </th>
                <td className="px-3 py-2.5 text-right">{t.won ? fmt.peso(t.won) : <span className="text-ink-3">—</span>}</td>
                <td className="px-3 py-2.5 text-right">{t.quoted ? fmt.peso(t.quoted) : <span className="text-ink-3">—</span>}</td>
                <td className="px-3 py-2.5 text-right">{t.done}</td>
                <td className={`px-5 py-2.5 text-right ${t.overdue ? "font-semibold text-danger" : "text-ink-3"}`}>{t.overdue}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <table className="w-full min-w-[44rem] text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-meta text-ink-3">
              <Head k="name" first>
                Person
              </Head>
              <Head k="won">Won this month</Head>
              <Head k="quoted">Quoted this month</Head>
              <Head k="done">Activities this week</Head>
              <Head k="overdue">Overdue</Head>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule tabular-nums">
            {shown.map((p) => (
              <tr key={p.id} className="hover:bg-bench/40">
                <th scope="row" className="px-5 py-2.5 text-left font-normal">
                  <Link href={`/admin/users/${p.id}`} className="flex items-center gap-2.5">
                    <Avatar name={p.name} id={p.id} size="sm" />
                    <span className="min-w-0">
                      <span className="block font-medium text-ink hover:underline">{p.name}</span>
                      <span className="block text-meta text-ink-3">{p.team?.name ?? "No team"}</span>
                    </span>
                  </Link>
                </th>
                <td className="px-3 py-2.5 text-right">
                  {p.wonCentavos ? fmt.peso(p.wonCentavos) : <span className="text-ink-3">—</span>}
                  {p.wonCount > 0 && <span className="block text-meta text-ink-3">{fmt.plural(p.wonCount, "deal")}</span>}
                </td>
                <td className="px-3 py-2.5 text-right">
                  {p.quotesThisMonth ? fmt.peso(p.quotedThisMonthCentavos) : <span className="text-ink-3">—</span>}
                  {p.quotesThisMonth > 0 && <span className="block text-meta text-ink-3">{fmt.plural(p.quotesThisMonth, "quote")}</span>}
                </td>
                <td className={`px-3 py-2.5 text-right ${p.doneThisWeek ? "" : "text-ink-3"}`}>{p.doneThisWeek}</td>
                <td className={`px-3 py-2.5 text-right ${p.overdue ? "font-semibold text-danger" : "text-ink-3"}`}>{p.overdue}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Sheet>
  );
}

const SmallLink = ({ href, children }: { href: string; children: ReactNode }) => (
  <Link href={href} className="text-meta text-ink hover:underline">
    {children}
  </Link>
);

