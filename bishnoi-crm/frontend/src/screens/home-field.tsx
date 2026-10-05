import Link from "next/link";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Me, Org, Paged } from "@/src/platform/lib/types";
import { LogVisitButton } from "../components/field/log-visit";
import { Meters } from "../components/field/meters";
import type { Doctors, Performance, Visit } from "../components/field/types";
import { VisitList } from "../components/field/visit-list";

/** A field agent's day: how the month is going against their goals, who owes
 *  the most, and what they logged lately. Logging a visit is the one big button. */
export async function FieldHome({ me }: { me: Me & { org: Org } }) {
  const fmt = makeFormat(me.org);
  const [month, doctors, visits] = await Promise.all([
    load<Performance>("/field/performance"),
    load<Doctors>("/field/doctors?limit=500"),
    load<Paged<Visit>>("/visits?limit=8"),
  ]);
  const mine = month.people[0];
  const owing = doctors.items.filter((d) => (d.balance?.owedCentavos ?? 0) > 0).slice(0, 8);
  const today = fmt.todayKey();

  return (
    <>
      <PageHeader
        title={`${fmt.greeting()}, ${me.user.fullName.split(" ")[0]}`}
        actions={
          <LogVisitButton requireLocation variant="primary" org={me.org} now={new Date().toISOString()} doctors={doctors.items.map((d) => ({ id: d.id, name: d.name }))} />
        }
      >
        {fmt.monthLabel(month.month)}: your visits and collections against your goals.{" "}
        <Link href="/field/routes" className="text-hema hover:underline">
          Your route today
        </Link>
      </PageHeader>

      {mine && <Meters actual={mine.actual} goal={mine.goal} fmt={fmt} />}

      <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
        <Sheet className="px-5 pt-4 pb-3">
          <SectionTitle
            icon="money"
            action={
              <Link href="/field/doctors" className="text-meta text-hema hover:underline">
                All your doctors
              </Link>
            }
          >
            Who owes the most
          </SectionTitle>
          {owing.length === 0 ? (
            <p className="py-4 text-meta text-ink-3">Nobody owes anything on file. Balances come from accounting&apos;s upload.</p>
          ) : (
            <ul className="mt-1 divide-y divide-rule">
              {owing.map((d) => (
                <li key={d.id} className="flex items-baseline gap-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <Link href={`/companies/${d.id}`} className="font-medium text-hema hover:underline">
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

        <Sheet className="px-5 pt-4 pb-3">
          <SectionTitle
            icon="visit"
            action={
              visits.total > visits.items.length && (
                <Link href="/visits" className="text-meta text-hema hover:underline">
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
            <VisitList visits={visits.items} fmt={fmt} today={today} showWho={false} />
          )}
        </Sheet>
      </div>
    </>
  );
}
