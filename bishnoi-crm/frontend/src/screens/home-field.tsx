import Link from "next/link";
import { AttentionPanel } from "../components/attention-panel";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { loadQuery } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Me, Org, Paged } from "@/src/platform/lib/types";
import { LogVisitButton } from "../components/field/log-visit";
import type { Figure } from "../components/deals/figure-card";
import { MonthCard, paceFigure } from "../components/kpis/performance";
import type { Doctors, Performance, Visit } from "../components/field/types";
import { VisitList } from "../components/field/visit-list";
import { lower, termsOf, worded } from "../components/terms/terms";
import { MEASURES } from "../components/field/words";

/** A field agent's day: how the month is going against their goals, who owes
 *  the most, and what they logged lately. Logging a visit is the one big button. */
export async function FieldHome({ me }: { me: Me & { org: Org } }) {
  const fmt = makeFormat(me.org);
  // Home's one request.
  const { month, doctors, visits } = await loadQuery<{ month: Performance; doctors: Doctors; visits: Paged<Visit> }>(
    `query FieldHome { month: fieldPerformance doctors: fieldDoctors(limit: 500) visits(limit: 8) }`,
    {},
    ["month", "doctors", "visits"],
  );
  const mine = month.people[0];
  const owing = doctors.items.filter((d) => (d.balance?.owedCentavos ?? 0) > 0).slice(0, 8);
  const today = fmt.todayKey();
  // The month against the goals: the first goal (doctors visited) leads, the rest are tiles.
  const start = `${month.month}-01`;
  const [y, m] = month.month.split("-").map(Number);
  const end = `${month.month}-${String(new Date(Date.UTC(y, m, 0)).getUTCDate()).padStart(2, "0")}`;
  const goals: Figure[] = mine
    ? MEASURES.map((g) => {
        const show = (n: number) => (g.money ? fmt.peso(n) : String(n));
        return paceFigure({ value: show(mine.actual[g.key]), label: worded(g.label, termsOf(me)), actual: mine.actual[g.key], target: mine.goal?.[g.key], start, end, today, show, href: "/field", noTarget: "No goal set" });
      })
    : [];
  const [lead, ...tiles] = goals;

  return (
    <>
      <PageHeader
        title={`${fmt.greeting()}, ${me.user.fullName.split(" ")[0]}`}
        actions={
          <LogVisitButton requireLocation variant="primary" org={me.org} now={new Date().toISOString()} doctors={doctors.items.map((d) => ({ id: d.id, name: d.name }))} />
        }
      >
        {fmt.monthLabel(month.month)}: your visits and collections against your goals.{" "}
        <Link href="/field/routes" className="text-ink hover:underline">
          Your route today
        </Link>
      </PageHeader>
      <AttentionPanel />

      {/* Who to collect from next, widest; beside it, the month against the goals in one card. */}
      <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex flex-col">
        <Sheet className="flex-1 px-5 pt-4 pb-3">
          <SectionTitle
            icon="money"
            action={
              <Link href="/field/doctors" className="text-meta text-ink hover:underline">
                All your doctors
              </Link>
            }
          >
            Who owes the most
          </SectionTitle>
          {owing.length === 0 ? (
            <Empty compact icon="money" title="Nobody owes anything on file">Balances come from accounting&apos;s upload, with who to collect from first.</Empty>
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
        <div className="flex flex-col">
          {lead && <MonthCard title="Your month" subtitle={`${fmt.monthLabel(month.month)} so far, against your goals`} lead={lead} rest={tiles} />}
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
          Your recent visits
        </SectionTitle>
        {visits.items.length === 0 ? (
          <Empty
            title="No visits yet"
            icon="visit"
            actions={<LogVisitButton requireLocation org={me.org} now={new Date().toISOString()} doctors={doctors.items.map((d) => ({ id: d.id, name: d.name }))} />}
          >
            After each visit, use Log visit: what came of it, and any payment collected.
          </Empty>
        ) : (
          <VisitList visits={visits.items} fmt={fmt} today={today} showWho={false} site={lower(termsOf(me).site)} />
        )}
      </Sheet>
    </>
  );
}
