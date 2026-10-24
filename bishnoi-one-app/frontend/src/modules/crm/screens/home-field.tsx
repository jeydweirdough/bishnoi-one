import Link from "next/link";
import { Suspense } from "react";
import { AttentionPanel } from "@/src/modules/crm/components/attention-panel";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { Later } from "@/src/platform/ui/later";
import { Chart, ListRows } from "@/src/platform/ui/skeleton";
import { loadQuery } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Me, Org, Paged } from "@/src/platform/lib/types";
import { CardLink, Overview, OverviewLoading, type Stat } from "@/src/modules/crm/components/dashboard/parts";
import { LogVisitButton } from "@/src/modules/crm/components/field/log-visit";
import { paceFigure } from "@/src/modules/crm/components/kpis/performance";
import type { Coverage, Doctors, Performance, Visit } from "@/src/modules/crm/components/field/types";
import { CoverageCard } from "@/src/modules/crm/components/field/coverage";
import { ZoneTag } from "@/src/modules/crm/components/field/plan";
import { VisitList } from "@/src/modules/crm/components/field/visit-list";
import { lower, termsOf } from "@/src/modules/crm/components/terms/terms";

type FieldData = { month: Performance; doctors: Doctors; visits: Paged<Visit>; coverage: Coverage };

/**
 * A field agent's dashboard: the month in four figures against their goals
 * (accounts visited, collected, coverage, still owed); who to see first beside
 * coverage; then who owes the most and what was logged lately. Logging a visit
 * is the one big button.
 */
export function FieldHome({ me }: { me: Me & { org: Org } }) {
  const fmt = makeFormat(me.org);
  const terms = termsOf(me);
  // Home's one request, asked for and not waited on: the greeting and every card's frame are drawn now.
  const answer = loadQuery<FieldData>(
    `query FieldHome { month: fieldPerformance doctors: fieldDoctors(limit: 500, sort: "plan") visits(limit: 4) coverage: fieldCoverage }`,
    {},
    ["month", "doctors", "visits", "coverage"],
  );
  return (
    <>
      <PageHeader
        title="Dashboard"
        actions={
          <Later data={answer} fallback={null}>
            {({ doctors }) => (
              <LogVisitButton requireLocation variant="primary" org={me.org} now={new Date().toISOString()} doctors={doctors.items.map((d) => ({ id: d.id, name: d.name, pin: d.pin, zone: d.zone }))} />
            )}
          </Later>
        }
      >
        {fmt.greeting()}, {me.user.fullName.split(" ")[0]}. {fmt.monthLabel(fmt.todayKey().slice(0, 7))}: your visits and collections against your goals.{" "}
        <Link href="/crm/field/routes" className="font-medium text-ink underline-offset-4 hover:underline">
          Today&apos;s route
        </Link>
      </PageHeader>
      <Suspense fallback={null}>
        <AttentionPanel />
      </Suspense>
      <Suspense fallback={<FieldLoading visited={terms.visited.many} />}>
        <FieldCards me={me} answer={answer} />
      </Suspense>
    </>
  );
}

/** The dashboard as it waits: each card already its own title, the figures to come. */
function FieldLoading({ visited }: { visited: string }) {
  const rows = (n: number) => (
    <div className="-mx-5">
      <ListRows rows={n} columns={2} />
    </div>
  );
  return (
    <>
      <OverviewLoading
        title="This month"
        stats={[
          { icon: "visit", label: `${visited} visited` },
          { icon: "payments", label: "Collected" },
          { icon: "goals", label: "Coverage" },
          { icon: "money", label: "Still owed" },
        ]}
      />
      <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Sheet className="px-5 py-4">
          <SectionTitle icon="visit">Priority visits</SectionTitle>
          {rows(5)}
        </Sheet>
        <Sheet className="px-5 py-4">
          <SectionTitle icon="goals">Coverage</SectionTitle>
          <div className="mt-4">
            <Chart bars={3} />
          </div>
        </Sheet>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Sheet className="px-5 py-4">
          <SectionTitle icon="money">Top outstanding balances</SectionTitle>
          {rows(5)}
        </Sheet>
        <Sheet className="px-5 py-4">
          <SectionTitle icon="visit">Recent visits</SectionTitle>
          {rows(5)}
        </Sheet>
      </div>
    </>
  );
}

async function FieldCards({ me, answer }: { me: Me & { org: Org }; answer: Promise<FieldData> }) {
  const fmt = makeFormat(me.org);
  const terms = termsOf(me);
  const { month, doctors, visits, coverage } = await answer;
  const mine = month.people[0];
  const owingAll = doctors.items.filter((d) => (d.balance?.owedCentavos ?? 0) > 0).sort((a, b) => b.balance!.owedCentavos - a.balance!.owedCentavos);
  const owing = owingAll.slice(0, 6);
  const owed = owingAll.reduce((n, d) => n + d.balance!.owedCentavos, 0);
  const asOf = owingAll.map((d) => d.balance!.asOf).sort().at(-1);
  // Who to see first, by the plan: red, then yellow, those still short of their visits this month.
  const first = doctors.items.filter((d) => (d.zone === "red" || d.zone === "yellow") && (!d.visitsNeeded || d.visitsThisMonth < d.visitsNeeded)).slice(0, 6);
  const zoned = doctors.items.some((d) => d.zone);
  const today = fmt.todayKey();
  const start = `${month.month}-01`;
  const [y, m] = month.month.split("-").map(Number);
  const end = `${month.month}-${String(new Date(Date.UTC(y, m, 0)).getUTCDate()).padStart(2, "0")}`;
  const pace = (key: "doctorsVisited" | "amountCentavos", label: string, money = false) =>
    mine
      ? paceFigure({ value: money ? fmt.peso(mine.actual[key]) : String(mine.actual[key]), label, actual: mine.actual[key], target: mine.goal?.[key], start, end, today, show: (n) => (money ? fmt.peso(n) : String(n)), href: "/crm/field", noTarget: "No target set" })
      : null;
  const visited = pace("doctorsVisited", `${terms.visited.many} visited`);
  const collected = pace("amountCentavos", "Collected", true);
  const pct = coverage.coveragePct;

  const stats: Stat[] = [
    {
      icon: "visit",
      label: `${terms.visited.many} visited`,
      href: "/crm/field",
      value: visited?.value ?? "0",
      pill: visited?.pill,
      note: (
        <>
          {visited?.note ?? "No target set"}
          {mine?.goal?.doctorsUpdated ? ` · ${mine.actual.doctorsUpdated} of ${mine.goal.doctorsUpdated} updated` : ""}
        </>
      ),
    },
    {
      icon: "payments",
      label: "Collected",
      href: "/crm/field",
      value: collected?.value ?? fmt.peso(0),
      pill: collected?.pill,
      note: (
        <>
          {collected?.note ?? "No target set"}
          {mine ? ` · ${mine.actual.collectionVisits}${mine.goal?.collectionVisits ? ` of ${mine.goal.collectionVisits}` : ""} collection visits` : ""}
        </>
      ),
    },
    {
      icon: "goals",
      label: "Coverage",
      href: "/crm/field/doctors",
      value: pct === null ? "—" : `${pct}%`,
      pill: pct === null ? undefined : pct >= coverage.goalPct ? { text: "On target", tone: "good" } : { text: "Below goal", tone: "warn" },
      note: `${coverage.visited} of ${coverage.doctors} ${lower(terms.visited.many)} · goal ${coverage.goalPct}%`,
    },
    {
      icon: "money",
      label: "Still owed",
      href: "/crm/field/doctors",
      value: fmt.peso(owed),
      note: owingAll.length ? `${owingAll.length} ${owingAll.length === 1 ? "owes" : "owe"}${asOf ? ` · balances as of ${fmt.dateLabel(asOf)}` : ""}` : "No outstanding balances",
    },
  ];

  return (
    <>
      <Overview title="This month" action={<CardLink href="/crm/field">View goals</CardLink>} stats={stats} />

      {/* Who to see first beside how much of the list has been covered. */}
      <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Sheet className="flex flex-col px-5 py-4">
          <SectionTitle icon="visit" action={<CardLink href="/crm/field/doctors">View plan</CardLink>}>
            Priority visits
          </SectionTitle>
          {!zoned ? (
            <div className="flex flex-1 flex-col justify-center">
              <Empty compact icon="visit" title="No zones set yet">
                Give each account a zone on the list (red, yellow, green) and the ones to see first show here.
              </Empty>
            </div>
          ) : first.length === 0 ? (
            <div className="flex flex-1 flex-col justify-center">
              <Empty compact icon="visit" title="Red and yellow zones covered">
                Every account in them has had this month&apos;s visits. Green zone next, in the afternoon.
              </Empty>
            </div>
          ) : (
            <ul className="mt-1 divide-y divide-rule">
              {first.map((d) => (
                <li key={d.id} className="flex items-center gap-3 py-2.5">
                  <ZoneTag zone={d.zone} />
                  <div className="min-w-0 flex-1">
                    <Link href={`/crm/companies/${d.id}`} className="block truncate font-medium text-ink hover:underline">
                      {d.name}
                    </Link>
                    <p className="truncate text-meta text-ink-3">
                      {d.tier ? `Tier ${d.tier} · ` : ""}
                      {d.city ?? ""}
                    </p>
                  </div>
                  <span className="shrink-0 text-meta text-ink-2 tabular-nums">
                    {d.visitsNeeded ? `${d.visitsThisMonth} of ${d.visitsNeeded}` : d.visitsThisMonth} visits
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Sheet>
        <CoverageCard coverage={coverage} monthName={fmt.monthLabel(coverage.month)} many={lower(terms.visited.many)} />
      </div>

      {/* Who owes the most, and what was logged lately. */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Sheet className="flex flex-col px-5 py-4">
          <SectionTitle icon="money" action={<CardLink href="/crm/field/doctors">All accounts</CardLink>}>
            Top outstanding balances
          </SectionTitle>
          {owing.length === 0 ? (
            <div className="flex flex-1 flex-col justify-center">
              <Empty compact icon="money" title="No outstanding balances">
                Balances come from the accounting upload.
              </Empty>
            </div>
          ) : (
            <ul className="mt-1 divide-y divide-rule">
              {owing.map((d) => (
                <li key={d.id} className="flex items-center gap-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <Link href={`/crm/companies/${d.id}`} className="block truncate font-medium text-ink hover:underline">
                      {d.name}
                    </Link>
                    <p className="truncate text-meta text-ink-3">
                      {d.lastVisitAt ? `Last visited ${fmt.whenLabel(d.lastVisitAt, today)}` : "Not visited yet"}
                      {d.city && <> · {d.city}</>}
                    </p>
                  </div>
                  <span className="shrink-0 font-semibold tabular-nums">{fmt.peso(d.balance!.owedCentavos)}</span>
                </li>
              ))}
            </ul>
          )}
        </Sheet>
        <Sheet className="flex flex-col px-5 py-4">
          <SectionTitle icon="visit" action={visits.total > visits.items.length && <CardLink href="/crm/visits">All {visits.total} visits</CardLink>}>
            Recent visits
          </SectionTitle>
          {visits.items.length === 0 ? (
            <div className="flex flex-1 flex-col justify-center">
              <Empty
                compact
                title="No visits yet"
                icon="visit"
                actions={<LogVisitButton requireLocation org={me.org} now={new Date().toISOString()} doctors={doctors.items.map((d) => ({ id: d.id, name: d.name, pin: d.pin, zone: d.zone }))} />}
              >
                After each visit, use Log visit to record the outcome and any payment collected.
              </Empty>
            </div>
          ) : (
            <div className="mt-1">
              <VisitList visits={visits.items} fmt={fmt} today={today} showWho={false} site={lower(terms.site)} />
            </div>
          )}
        </Sheet>
      </div>
    </>
  );
}
