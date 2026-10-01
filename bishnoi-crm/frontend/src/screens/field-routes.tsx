import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { NoAccess } from "../components/admin/words";
import { RouteMap } from "../components/field/route-map";
import type { Performance, Route, RouteDays } from "../components/field/types";
import { VisitList } from "../components/field/visit-list";
import { distanceText } from "../components/field/where";

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
  const q = new URLSearchParams();
  if (person) q.set("person", person);
  if (typeof sp.day === "string") q.set("day", sp.day);
  const route = await load<Route>(`/field/routes?${q}`);
  const days = await load<RouteDays>(`/field/routes/days?month=${route.day.slice(0, 7)}${person ? `&person=${enc(person)}` : ""}`);
  const fmt = makeFormat(me.org);
  const time = fmt.on({ hour: "numeric", minute: "2-digit" });
  const link = (day: string, who = person) => `/field/routes?${new URLSearchParams({ ...(who ? { person: who } : {}), day })}`;
  const atClinic = route.visits.filter((v) => v.atClinic === true).length;
  const elsewhere = route.visits.filter((v) => v.atClinic === false).length;
  const mine = route.person.id === me.user.id;

  return (
    <>
      <PageHeader title={mine ? "Your route" : `${route.person.name}'s route`} crumbs={watches ? [{ href: "/field", label: "Field work" }] : undefined}>
        Where {mine ? "you" : "they"} went while Bishnoi One was open, 6:00 to 20:00, and where each visit was logged.
      </PageHeader>

      {watches && people.length > 1 && (
        <nav aria-label="Person" className="mb-3 flex flex-wrap gap-1.5">
          {people.map((p) => (
            <Link
              key={p.id}
              href={link(route.day, p.id)}
              aria-current={p.id === route.person.id ? "page" : undefined}
              className={`rounded-[3px] border px-3 py-1.5 text-meta ${p.id === route.person.id ? "border-hema bg-hema-tint font-semibold text-hema" : "border-rule-strong text-ink-2 hover:border-control"}`}
            >
              {p.name}
            </Link>
          ))}
        </nav>
      )}

      <nav aria-label="Day" className="mb-4 flex items-center gap-2">
        <Link href={link(shiftDay(route.day, -1))} className="rounded-[3px] p-1.5 text-ink-2 hover:bg-bench" aria-label="The day before">
          <ChevronLeft className="size-4" aria-hidden />
        </Link>
        <span className="min-w-44 text-center text-heading">{route.day === route.today ? "Today" : fmt.dateLabel(route.day)}</span>
        {route.day < route.today ? (
          <Link href={link(shiftDay(route.day, 1))} className="rounded-[3px] p-1.5 text-ink-2 hover:bg-bench" aria-label="The day after">
            <ChevronRight className="size-4" aria-hidden />
          </Link>
        ) : (
          <span className="w-7" />
        )}
      </nav>

      <Sheet className="mb-5 grid grid-cols-2 gap-px overflow-hidden bg-rule sm:grid-cols-4 [&>*]:bg-sheet">
        <div className="px-5 py-4">
          <span className="block text-figure">{route.summary ? distanceText(route.summary.distanceM) : "—"}</span>
          <span className="block text-meta text-ink-3">Covered</span>
        </div>
        <div className="px-5 py-4">
          <span className="block text-figure">{route.summary ? time.format(new Date(route.summary.firstAt)) : "—"}</span>
          <span className="block text-meta text-ink-3">
            First seen{route.summary && <>, last {time.format(new Date(route.summary.lastAt))}</>}
          </span>
        </div>
        <div className="px-5 py-4">
          <span className="block text-figure">{route.visits.length}</span>
          <span className="block text-meta text-ink-3">{atClinic} at the clinic</span>
        </div>
        <div className="px-5 py-4">
          <span className={`block text-figure ${elsewhere ? "text-danger" : ""}`}>{elsewhere}</span>
          <span className="block text-meta text-ink-3">Logged away from the clinic</span>
        </div>
      </Sheet>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-start">
        <div className="space-y-5">
          <Sheet className="p-2">
            <RouteMap points={route.points} visits={route.visits} />
            {!route.points.length && <p className="px-3 pt-2 pb-1 text-meta text-ink-3">No trail this day: Bishnoi One wasn&apos;t open on their phone during work hours.</p>}
          </Sheet>
          <Sheet className="px-5 pt-4 pb-2">
            <SectionTitle icon="visit">Visits</SectionTitle>
            {route.visits.length ? (
              <VisitList visits={route.visits} fmt={fmt} today={route.today} showWho={false} />
            ) : (
              <p className="py-4 text-meta text-ink-3">No visits logged this day.</p>
            )}
          </Sheet>
        </div>
        <Sheet className="px-5 pt-4 pb-3">
          <SectionTitle icon="calendar">{fmt.monthLabel(days.month)}</SectionTitle>
          {days.days.length ? (
            <ul className="mt-1 divide-y divide-rule">
              {days.days.map((d) => (
                <li key={d.day}>
                  <Link href={link(d.day)} className={`flex justify-between py-2 text-sm hover:text-hema ${d.day === route.day ? "font-semibold text-hema" : ""}`}>
                    <span>{fmt.dateLabel(d.day)}</span>
                    <span className="tabular-nums text-ink-2">{distanceText(d.distanceM)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-3 text-meta text-ink-3">No days on the road yet this month.</p>
          )}
          <p className="mt-3 border-t border-rule pt-3 text-meta text-ink-3">Routes are kept {route.keptDays} days; each day&apos;s distance stays after that.</p>
        </Sheet>
      </div>
    </>
  );
}
