import Link from "next/link";
import { AttentionPanel } from "../components/attention-panel";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { loadQuery } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Me, Org, Paged } from "@/src/platform/lib/types";
import { LogVisitButton } from "../components/field/log-visit";
import type { Figure } from "../components/deals/figure-card";
import { MonthCard, paceFigure } from "../components/kpis/performance";
import type { Coverage, Doctors, Performance, Visit } from "../components/field/types";
import { CoverageCard } from "../components/field/coverage";
import { ZoneTag } from "../components/field/plan";
import { VisitList } from "../components/field/visit-list";
import { lower, termsOf, worded } from "../components/terms/terms";
import { MEASURES } from "../components/field/words";

/** A field agent's day: how the month is going against their goals, who owes
 *  the most, and what they logged lately. Logging a visit is the one big button. */
export async function FieldHome({ me }: { me: Me & { org: Org } }) {
  const fmt = makeFormat(me.org);
  // Home's one request.
  const { month, doctors, visits, coverage } = await loadQuery<{ month: Performance; doctors: Doctors; visits: Paged<Visit>; coverage: Coverage }>(
    `query FieldHome { month: fieldPerformance doctors: fieldDoctors(limit: 500, sort: "plan") visits(limit: 8) coverage: fieldCoverage }`,
    {},
    ["month", "doctors", "visits", "coverage"],
  );
  const mine = month.people[0];
  const owing = doctors.items
    .filter((d) => (d.balance?.owedCentavos ?? 0) > 0)
    .sort((a, b) => b.balance!.owedCentavos - a.balance!.owedCentavos)
    .slice(0, 8);
  // Who to see first, by the plan: red, then yellow, those still short of their visits this month.
  const first = doctors.items.filter((d) => (d.zone === "red" || d.zone === "yellow") && (!d.visitsNeeded || d.visitsThisMonth < d.visitsNeeded)).slice(0, 8);
  const zoned = doctors.items.some((d) => d.zone);
  const today = fmt.todayKey();
  // The month against the goals: the first goal (doctors visited) leads, the rest are tiles.
  const start = `${month.month}-01`;
  const [y, m] = month.month.split("-").map(Number);
  const end = `${month.month}-${String(new Date(Date.UTC(y, m, 0)).getUTCDate()).padStart(2, "0")}`;
  const goals: Figure[] = mine
    ? MEASURES.map((g) => {
        const show = (n: number) => (g.money ? fmt.peso(n) : String(n));
        return paceFigure({ value: show(mine.actual[g.key]), label: worded(g.label, termsOf(me)), actual: mine.actual[g.key], target: mine.goal?.[g.key], start, end, today, show, href: "/field", noTarget: "No target set" });
      })
    : [];
  const [lead, ...tiles] = goals;

  return (
    <>
      <PageHeader
        title={`${fmt.greeting()}, ${me.user.fullName.split(" ")[0]}`}
        actions={
          <LogVisitButton requireLocation variant="primary" org={me.org} now={new Date().toISOString()} doctors={doctors.items.map((d) => ({ id: d.id, name: d.name, pin: d.pin, zone: d.zone }))} />
        }
      >
        {fmt.monthLabel(month.month)}: your visits and collections against your goals.{" "}
        <Link href="/field/routes" className="text-ink hover:underline">
          Today&apos;s route
        </Link>
      </PageHeader>
      <AttentionPanel />

      {/* Who to collect from next, widest; beside it, the month against the goals in one card. */}
      <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex flex-col gap-5">
        {zoned && (
          <Sheet className="px-5 pt-4 pb-3">
            <SectionTitle
              icon="visit"
              action={
                <Link href="/field/doctors" className="text-meta text-ink hover:underline">
                  View plan
                </Link>
              }
            >
              Priority visits
            </SectionTitle>
            {first.length === 0 ? (
              <Empty compact icon="visit" title="Red and yellow zones covered">
                Every doctor in them has had this month&apos;s visits. Green zone next, in the afternoon.
              </Empty>
            ) : (
              <ul className="mt-1 divide-y divide-rule">
                {first.map((d) => (
                  <li key={d.id} className="flex items-center gap-3 py-2.5">
                    <ZoneTag zone={d.zone} />
                    <div className="min-w-0 flex-1">
                      <Link href={`/companies/${d.id}`} className="font-medium text-ink hover:underline">
                        {d.name}
                      </Link>
                      <p className="text-meta text-ink-3">
                        {d.tier ? `Tier ${d.tier} · ` : ""}
                        {d.visitsNeeded ? `${d.visitsThisMonth} of ${d.visitsNeeded} visits this month` : `${d.visitsThisMonth} visits this month`}
                        {d.city && <> · {d.city}</>}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Sheet>
        )}
        <Sheet className="flex-1 px-5 pt-4 pb-3">
          <SectionTitle
            icon="money"
            action={
              <Link href="/field/doctors" className="text-meta text-ink hover:underline">
                All doctors
              </Link>
            }
          >
            Top outstanding balances
          </SectionTitle>
          {owing.length === 0 ? (
            <Empty compact icon="money" title="No outstanding balances">Balances come from the accounting upload.</Empty>
          ) : (
            <ul className="mt-1 divide-y divide-rule">
              {owing.map((d) => (
                <li key={d.id} className="flex items-baseline gap-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <Link href={`/companies/${d.id}`} className="font-medium text-ink hover:underline">
                      {d.name}
                    </Link>
                    <p className="text-meta text-ink-3">
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
        </div>
        <div className="flex flex-col gap-5">
          <CoverageCard coverage={coverage} monthName={fmt.monthLabel(coverage.month)} many={lower(termsOf(me).visited.many)} />
          {lead && <MonthCard title="Monthly performance" subtitle={`${fmt.monthLabel(month.month)} to date, against targets`} lead={lead} rest={tiles} />}
        </div>
      </div>

      {/* Then what was logged lately. */}
      <Sheet className="px-5 pt-4 pb-3">
        <SectionTitle
          icon="visit"
          action={
            visits.total > visits.items.length && (
              <Link href="/visits" className="text-meta text-ink hover:underline">
                See all {visits.total}
              </Link>
            )
          }
        >
          Recent visits
        </SectionTitle>
        {visits.items.length === 0 ? (
          <Empty
            title="No visits yet"
            icon="visit"
            actions={<LogVisitButton requireLocation org={me.org} now={new Date().toISOString()} doctors={doctors.items.map((d) => ({ id: d.id, name: d.name, pin: d.pin, zone: d.zone }))} />}
          >
            After each visit, use Log visit to record the outcome and any payment collected.
          </Empty>
        ) : (
          <VisitList visits={visits.items} fmt={fmt} today={today} showWho={false} site={lower(termsOf(me).site)} />
        )}
      </Sheet>
    </>
  );
}
