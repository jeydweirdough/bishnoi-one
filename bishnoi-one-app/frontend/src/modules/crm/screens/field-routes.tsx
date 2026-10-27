import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { PageHeader, SectionTitle, Sheet, Empty } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { WeekBoard } from "@/src/modules/crm/components/field/week-board";
import { ZoneTag } from "@/src/modules/crm/components/field/plan";
import { RouteMap } from "@/src/modules/crm/components/field/route-map";
import type { Doctors, Performance, Route, RouteDays, WeekPlan } from "@/src/modules/crm/components/field/types";
import { VisitList } from "@/src/modules/crm/components/field/visit-list";
import { distanceText } from "@/src/modules/crm/components/field/where";
import { lower, termsOf } from "@/src/modules/crm/components/terms/terms";

export const metadata = { title: "Route" };

/** The day before or after "2026-09-25". */
function shiftDay(day: string, by: number): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + by);
  return d.toISOString().slice(0, 10);
}

/**
 * One person's day on the road: where they went while the CRM was open (in
 * work hours), and where each visit was logged against its clinic. Their lead
 * and the admin see anyone within reach; an agent sees their own.
 */
export default async function FieldRoutesPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  const watches = can(me, "goals.view");
  if (!watches && !can(me, "visits.create")) return <NoAccess what="routes" />;
  const sp = await searchParams;
  const people = watches ? (await load<Performance>("/field/performance")).people.map((p) => p.person) : [];
  const person = typeof sp.person === "string" ? sp.person : watches ? (people[0]?.id ?? "") : "";
  // The week's plan first (the playbook's routing map); the day on the road beside it.
  if (sp.view !== "day") return <PlanView me={me} people={people} person={person} week={typeof sp.week === "string" ? sp.week : ""} watches={watches} />;
  const q = new URLSearchParams();
  if (person) q.set("person", person);
  if (typeof sp.day === "string") q.set("day", sp.day);
  const route = await load<Route>(`/field/routes?${q}`);
  const days = await load<RouteDays>(`/field/routes/days?month=${route.day.slice(0, 7)}${person ? `&person=${enc(person)}` : ""}`);
  const fmt = makeFormat(me.org);
  const time = fmt.on({ hour: "numeric", minute: "2-digit" });
  const link = (day: string, who = person) => `/crm/field/routes?${new URLSearchParams({ view: "day", ...(who ? { person: who } : {}), day })}`;
  const atClinic = route.visits.filter((v) => v.atClinic === true).length;
  const elsewhere = route.visits.filter((v) => v.atClinic === false).length;
  const mine = route.person.id === me.user.id;

  return (
    <>
      <PageHeader title={mine ? "Daily route" : `Daily route: ${route.person.name}`} crumbs={watches ? [{ href: "/crm/field", label: "Field work" }] : undefined}>
        Where {mine ? "you" : "they"} went while Bishnoi One was open, 6:00 to 20:00, and where each visit was logged.
      </PageHeader>

      <People people={watches ? people : []} current={route.person.id} href={(id) => link(route.day, id)} />
      <Views current="day" person={person} />

      <nav aria-label="Day" className="mb-4 flex items-center gap-2">
        <Link href={link(shiftDay(route.day, -1))} className="rounded-md p-1.5 text-ink-2 hover:bg-bench" aria-label="Previous day">
          <ChevronLeft className="size-4" aria-hidden />
        </Link>
        <span className="min-w-44 text-center text-heading">{route.day === route.today ? "Today" : fmt.dateLabel(route.day)}</span>
        {route.day < route.today ? (
          <Link href={link(shiftDay(route.day, 1))} className="rounded-md p-1.5 text-ink-2 hover:bg-bench" aria-label="Next day">
            <ChevronRight className="size-4" aria-hidden />
          </Link>
        ) : (
          <span className="w-7" />
        )}
      </nav>

      <Sheet className="mb-5 grid grid-cols-2 gap-px overflow-hidden bg-rule sm:grid-cols-4 [&>*]:bg-sheet">
        <div className="px-5 py-4">
          <span className="block text-figure">{route.summary ? distanceText(route.summary.distanceM) : "—"}</span>
          <span className="block text-meta text-ink-3">Distance</span>
        </div>
        <div className="px-5 py-4">
          <span className="block text-figure">{route.summary ? time.format(new Date(route.summary.firstAt)) : "—"}</span>
          <span className="block text-meta text-ink-3">
            First activity{route.summary && <>, last {time.format(new Date(route.summary.lastAt))}</>}
          </span>
        </div>
        <div className="px-5 py-4">
          <span className="block text-figure">{route.visits.length}</span>
          <span className="block text-meta text-ink-3">{atClinic} at the {lower(termsOf(me).site)}</span>
        </div>
        <div className="px-5 py-4">
          <span className={`block text-figure ${elsewhere ? "text-danger" : ""}`}>{elsewhere}</span>
          <span className="block text-meta text-ink-3">Logged away from the {lower(termsOf(me).site)}</span>
        </div>
      </Sheet>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-start">
        <div className="space-y-5">
          <Sheet className="p-2">
            <RouteMap points={route.points} visits={route.visits} />
            {!route.points.length && <p className="px-3 pt-2 pb-1 text-meta text-ink-3">No location data for this day: Bishnoi One wasn&apos;t open on their phone during work hours.</p>}
          </Sheet>
          <Sheet className="px-5 pt-4 pb-2">
            <SectionTitle icon="visit">Visits</SectionTitle>
            {route.visits.length ? (
              <VisitList visits={route.visits} fmt={fmt} today={route.today} showWho={false} site={lower(termsOf(me).site)} />
            ) : (
              <Empty compact icon="visit" title="No visits this day">Visits logged with their location show here as a route.</Empty>
            )}
          </Sheet>
        </div>
        <div className="space-y-5">
        <Sheet className="px-5 pt-4 pb-3">
          <SectionTitle icon="visit">Planned</SectionTitle>
          {route.planned.length ? (
            <ul className="mt-1 divide-y divide-rule">
              {route.planned.map((p) => (
                <li key={p.id} className="flex items-center gap-2 py-2 text-sm">
                  <ZoneTag zone={p.doctor.zone} />
                  <Link href={`/crm/customers/${p.doctor.id}`} className="min-w-0 flex-1 truncate text-ink hover:underline">
                    {p.doctor.name}
                  </Link>
                  <span className={`text-meta ${p.visited ? "font-semibold text-filed" : "text-ink-3"}`}>{p.visited ? "Visited" : "Not visited"}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty compact icon="visit" title="No planned visits">
              Visits are planned under Weekly plan.
            </Empty>
          )}
        </Sheet>
        <Sheet className="px-5 pt-4 pb-3">
          <SectionTitle icon="calendar">{fmt.monthLabel(days.month)}</SectionTitle>
          {days.days.length ? (
            <ul className="mt-1 divide-y divide-rule">
              {days.days.map((d) => (
                <li key={d.day}>
                  <Link href={link(d.day)} className={`flex justify-between py-2 text-sm hover:text-ink ${d.day === route.day ? "font-semibold text-ink" : ""}`}>
                    <span>{fmt.dateLabel(d.day)}</span>
                    <span className="tabular-nums text-ink-2">{distanceText(d.distanceM)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <Empty compact icon="trend" title="No route days">Each day with a visit logged shows here, this month.</Empty>
          )}
          <p className="mt-3 border-t border-rule pt-3 text-meta text-ink-3">Routes are kept {route.keptDays} days; each day&apos;s distance stays after that.</p>
        </Sheet>
        </div>
      </div>
    </>
  );
}

type Person = { id: string; name: string };

/** Whose: a lead's people, one at a time. */
function People({ people, current, href }: { people: Person[]; current: string; href: (id: string) => string }) {
  if (people.length < 2) return null;
  return (
    <nav aria-label="Person" className="mb-3 flex flex-wrap gap-1.5">
      {people.map((p) => (
        <Link
          key={p.id}
          href={href(p.id)}
          aria-current={p.id === current ? "page" : undefined}
          className={`rounded-md border px-3 py-1.5 text-meta ${p.id === current ? "border-hema bg-hema-tint font-semibold text-ink" : "border-rule-strong text-ink-2 hover:border-control"}`}
        >
          {p.name}
        </Link>
      ))}
    </nav>
  );
}

function Views({ current, person }: { current: "plan" | "day"; person: string }) {
  const who: Record<string, string> = person ? { person } : {};
  return (
    <div className="mb-4">
      <ToggleLinks
        current={current}
        options={[
          { value: "plan", label: "Weekly plan", href: `/crm/field/routes?${new URLSearchParams(who)}` },
          { value: "day", label: "Daily route", href: `/crm/field/routes?${new URLSearchParams({ view: "day", ...who })}` },
        ]}
      />
    </div>
  );
}

/** The week's plan by zone (Rx playbook): planned by the agent, gone over by their coach. */
async function PlanView({ me, people, person, week, watches }: { me: Awaited<ReturnType<typeof getCompanyMe>>; people: Person[]; person: string; week: string; watches: boolean }) {
  const q = new URLSearchParams({ ...(person ? { person } : {}), ...(week ? { week } : {}) });
  const plan = await load<WeekPlan>(`/field/plan?${q}`);
  // The doctors to add from: one's own, by the plan.
  const doctors = plan.can.plan ? (await load<Doctors>("/field/doctors?limit=500&sort=plan")).items : [];
  const fmt = makeFormat(me.org);
  const short = fmt.on({ weekday: "short", day: "numeric", timeZone: "UTC" });
  const long = fmt.on({ weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
  const at = (day: string) => new Date(`${day}T00:00:00Z`);
  const dayLabel = Object.fromEntries(plan.days.map((d) => [d.day, short.format(at(d.day))]));
  const fullDay = Object.fromEntries(plan.days.map((d) => [d.day, long.format(at(d.day))]));
  const link = (w: string, who = person) => `/crm/field/routes?${new URLSearchParams({ ...(who ? { person: who } : {}), week: w })}`;
  const mine = plan.person.id === me.user.id;
  const visited = plan.days.reduce((n, d) => n + d.stops.filter((s) => s.visited).length, 0);
  const planned = plan.days.reduce((n, d) => n + d.stops.length, 0);
  return (
    <>
      <PageHeader title={mine ? "Weekly plan" : `Weekly plan: ${plan.person.name}`} crumbs={watches ? [{ href: "/crm/field", label: "Field work" }] : undefined}>
        Red doctors in the morning, yellow midday, green in the afternoon: {plan.callsADay} a day, Monday to Friday. Saturday is for admin.
      </PageHeader>
      <People people={watches ? people : []} current={plan.person.id} href={(id) => link(plan.week, id)} />
      <Views current="plan" person={person} />
      <nav aria-label="Week" className="mb-4 flex flex-wrap items-center gap-2">
        <Link href={link(shiftDay(plan.week, -7))} className="rounded-md p-1.5 text-ink-2 hover:bg-bench" aria-label="Previous week">
          <ChevronLeft className="size-4" aria-hidden />
        </Link>
        <span className="min-w-44 text-center text-heading">
          {plan.week === plan.thisWeek ? "This week" : `Week of ${fmt.dateLabel(plan.week)}`}
        </span>
        <Link href={link(shiftDay(plan.week, 7))} className="rounded-md p-1.5 text-ink-2 hover:bg-bench" aria-label="Next week">
          <ChevronRight className="size-4" aria-hidden />
        </Link>
        {plan.week !== plan.thisWeek && (
          <Link href={link(plan.thisWeek)} className="text-meta text-ink hover:underline">
            This week
          </Link>
        )}
        <span className="ml-auto text-meta text-ink-3 tabular-nums">
          {visited} of {planned} planned visits completed
        </span>
      </nav>
      <WeekBoard plan={plan} doctors={doctors} dayLabel={dayLabel} fullDay={fullDay} />
    </>
  );
}
