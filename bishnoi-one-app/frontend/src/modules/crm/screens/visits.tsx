import { ChevronLeft, ChevronRight } from "lucide-react";
import { Pager } from "@/src/platform/ui/pager";
import { pageOf, slicePage } from "@/src/platform/ui/paging";
import Link from "next/link";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Paged } from "@/src/platform/lib/types";
import { LinkButton } from "@/src/platform/ui/button";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { LogVisitButton } from "@/src/modules/crm/components/field/log-visit";
import type { Doctors, Performance, Visit } from "@/src/modules/crm/components/field/types";
import { VisitList } from "@/src/modules/crm/components/field/visit-list";
import { isFieldAgent, shiftMonth } from "@/src/modules/crm/components/field/words";
import { lower, termsOf } from "@/src/modules/crm/components/terms/terms";

export const metadata = { title: "Visits" };

/** Every visit in a month, newest first: one person's (from the tracker) or everyone's within reach. */
export default async function VisitsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  if (!can(me, "visits.view")) return <NoAccess what="visits" />;
  const sp = await searchParams;
  const person = typeof sp.person === "string" ? sp.person : "";
  const perf = await load<Performance>(`/field/performance${typeof sp.month === "string" ? `?month=${enc(sp.month)}` : ""}`);
  const month = perf.month;
  const agent = isFieldAgent(me);
  const [visits, doctors] = await Promise.all([
    load<Paged<Visit>>(`/visits?limit=200&month=${month}${person ? `&person=${enc(person)}` : ""}`),
    // Only a field agent logs visits from here; the list is theirs to pick from.
    agent ? load<Doctors>("/field/doctors?limit=500") : null,
  ]);
  const fmt = makeFormat(me.org);
  const who = person ? perf.people.find((p) => p.person.id === person)?.person.name : null;
  const collected = visits.items.filter((v) => v.outcome === "collected").reduce((sum, v) => sum + v.amountCentavos, 0);
  // A month's visits are all in hand (the total collected is theirs), so a page is a slice.
  const shown = slicePage(visits.items, pageOf(sp.page));
  const link = (m: string) => `/crm/visits?month=${m}${person ? `&person=${person}` : ""}`;

  return (
    <>
      <PageHeader
        title={who ? `${who}'s visits` : "Visits"}
        crumbs={can(me, "goals.view") ? [{ href: `/crm/field?month=${month}`, label: "Field work" }] : undefined}
        actions={can(me, "visits.create") && <LogVisitButton variant="primary" />}
      >
        {visits.total} {visits.total === 1 ? "visit" : "visits"} · {fmt.peso(collected)} collected
      </PageHeader>
      <nav aria-label="Month" className="mb-4 flex items-center gap-2">
        <Link href={link(shiftMonth(month, -1))} className="rounded-md p-1.5 text-ink-2 hover:bg-bench" aria-label="Previous month">
          <ChevronLeft className="size-4" aria-hidden />
        </Link>
        <span className="min-w-36 text-center text-heading">
          {fmt.monthLabel(month)} {month.slice(0, 4)}
        </span>
        {month < perf.thisMonth && (
          <Link href={link(shiftMonth(month, 1))} className="rounded-md p-1.5 text-ink-2 hover:bg-bench" aria-label="Next month">
            <ChevronRight className="size-4" aria-hidden />
          </Link>
        )}
        {person && (
          <Link href={`/crm/visits?month=${month}`} className="ml-2 text-meta text-ink hover:underline">
            Everyone&apos;s
          </Link>
        )}
      </nav>
      <Sheet className="px-5 pt-1 pb-2">
        {visits.items.length === 0 ? (
          <Empty
            title="No visits this month"
            icon="visit"
            actions={
              doctors ? (
                <LogVisitButton requireLocation variant="primary" org={me.org} now={new Date().toISOString()} doctors={doctors.items.map((d) => ({ id: d.id, name: d.name, pin: d.pin, zone: d.zone }))} />
              ) : (
                can(me, "goals.view") && <LinkButton href={`/crm/field?month=${month}`}>View team progress</LinkButton>
              )
            }
          >
            Visits show up here as they&apos;re logged.
          </Empty>
        ) : (
          <VisitList visits={shown.rows} fmt={fmt} today={fmt.todayKey()} showWho={me.role?.scope !== "own"} site={lower(termsOf(me).site)} />
        )}
      </Sheet>
      <Pager total={visits.items.length} page={shown.page} base={link(month)} />
    </>
  );
}
