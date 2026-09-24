import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Paged } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import type { Performance, Visit } from "../components/field/types";
import { VisitList } from "../components/field/visit-list";
import { shiftMonth } from "../components/field/words";

export const metadata = { title: "Visits" };

/** Every visit in a month, newest first: one person's (from the tracker) or everyone's within reach. */
export default async function VisitsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  if (!can(me, "visits.view")) return <NoAccess what="visits" />;
  const sp = await searchParams;
  const person = typeof sp.person === "string" ? sp.person : "";
  const perf = await load<Performance>(`/field/performance${typeof sp.month === "string" ? `?month=${enc(sp.month)}` : ""}`);
  const month = perf.month;
  const visits = await load<Paged<Visit>>(`/visits?limit=200&month=${month}${person ? `&person=${enc(person)}` : ""}`);
  const fmt = makeFormat(me.org);
  const who = person ? perf.people.find((p) => p.person.id === person)?.person.name : null;
  const collected = visits.items.filter((v) => v.outcome === "collected").reduce((sum, v) => sum + v.amountCentavos, 0);
  const link = (m: string) => `/visits?month=${m}${person ? `&person=${person}` : ""}`;

  return (
    <>
      <PageHeader title={who ? `${who}'s visits` : "Visits"} crumbs={can(me, "goals.view") ? [{ href: `/field?month=${month}`, label: "Field work" }] : undefined}>
        {visits.total} {visits.total === 1 ? "visit" : "visits"} · {fmt.peso(collected)} collected
      </PageHeader>
      <nav aria-label="Month" className="mb-4 flex items-center gap-2">
        <Link href={link(shiftMonth(month, -1))} className="rounded-[3px] p-1.5 text-ink-2 hover:bg-bench" aria-label="The month before">
          <ChevronLeft className="size-4" aria-hidden />
        </Link>
        <span className="min-w-36 text-center text-heading">
          {fmt.monthLabel(month)} {month.slice(0, 4)}
        </span>
        {month < perf.thisMonth && (
          <Link href={link(shiftMonth(month, 1))} className="rounded-[3px] p-1.5 text-ink-2 hover:bg-bench" aria-label="The month after">
            <ChevronRight className="size-4" aria-hidden />
          </Link>
        )}
        {person && (
          <Link href={`/visits?month=${month}`} className="ml-2 text-meta text-hema hover:underline">
            Everyone&apos;s
          </Link>
        )}
      </nav>
      <Sheet className="px-5 pt-1 pb-2">
        {visits.items.length === 0 ? (
          <Empty title="No visits this month" icon="visit">
            Visits show up here as they&apos;re logged.
          </Empty>
        ) : (
          <VisitList visits={visits.items} fmt={fmt} today={fmt.todayKey()} showWho={me.role?.scope !== "own"} />
        )}
      </Sheet>
    </>
  );
}
