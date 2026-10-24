// Incidents: what's broken for many people at once, now and before.
import Link from "next/link";
import { Empty, PageHeader, Sheet } from "@/src/modules/console/platform/ui/sheet";
import { load } from "@/src/modules/console/platform/lib/api";
import { IncidentSeverityMark, IncidentStatusMark, Tabs } from "@/src/modules/console/components/marks";
import { DeclareIncident } from "@/src/modules/console/components/incidents/incident-forms";
import { howLong, reach } from "@/src/modules/console/components/incidents/words";
import { Filters } from "@/src/modules/console/components/support/filters";
import type { Incident, IncidentKind, Options } from "@/src/modules/console/lib/types";
import { INCIDENT_KINDS, plural, when } from "@/src/modules/console/lib/words";

export const metadata = { title: "Incidents" };

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export default async function IncidentsPage({ searchParams }: { searchParams: Search }) {
  const params = await searchParams;
  const resolved = one(params.state) === "resolved";
  const kind = one(params.kind) in INCIDENT_KINDS ? (one(params.kind) as IncidentKind) : "";
  const query = new URLSearchParams({ state: resolved ? "resolved" : "active" });
  if (kind) query.set("kind", kind);
  const [list, options] = await Promise.all([
    load<{ incidents: Incident[]; active: number }>(`/platform/incidents?${query}`),
    load<Options>("/platform/options"),
  ]);
  const tabHref = (state: string) => {
    const q = new URLSearchParams();
    if (state) q.set("state", state);
    if (kind) q.set("kind", kind);
    return `/platform/console/incidents${q.size ? `?${q}` : ""}`;
  };

  return (
    <>
      <PageHeader title="Incidents" actions={<DeclareIncident options={options} />}>
        When something is broken for many people at once. A ticket is one person&apos;s report; an incident says the platform knows, and is on it.
      </PageHeader>
      <Tabs
        current={resolved ? "resolved" : "active"}
        tabs={[
          { key: "active", label: "Active", href: tabHref(""), count: list.active },
          { key: "resolved", label: "Resolved", href: tabHref("resolved") },
        ]}
      />
      <Filters
        selects={[
          {
            name: "kind",
            label: "Type",
            options: [{ value: "", label: "All types" }, ...(Object.keys(INCIDENT_KINDS) as IncidentKind[]).map((k) => ({ value: k, label: INCIDENT_KINDS[k] }))],
          },
        ]}
      />
      <Sheet className="overflow-hidden">
        {list.incidents.length === 0 ? (
          <Empty icon="incidents" title={resolved ? "No resolved incidents." : kind ? `No active ${INCIDENT_KINDS[kind].toLowerCase()} incidents.` : "No active incidents."}>
            {resolved ? "Incidents appear here once an update marks them Resolved." : "When something breaks for many people at once, declare an incident so everyone works from the same page."}
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {list.incidents.map((i) => (
              <li key={i.id} className="px-5 py-3.5">
                <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1.5">
                  <p className="min-w-0">
                    <Link href={`/platform/console/incidents/${i.id}`} className="font-semibold text-hema hover:underline">
                      {i.number}
                    </Link>{" "}
                    <span className="text-ink">{i.title}</span>
                  </p>
                  <span className="flex shrink-0 items-center gap-3">
                    <IncidentSeverityMark severity={i.severity} />
                    <IncidentStatusMark status={i.status} />
                  </span>
                </div>
                <p className="mt-1 text-meta text-ink-2">
                  {INCIDENT_KINDS[i.kind]} · {i.companies.length > 0 && i.application ? `${i.application.name}, for ` : ""}
                  {reach(i)}
                </p>
                <p className="mt-0.5 text-meta text-ink-3">
                  <time dateTime={i.startedAt} title={when(i.startedAt)}>
                    {howLong(i)}
                  </time>
                  {" · "}
                  {i.lead ? `Led by ${i.lead.name}` : "No lead assigned"}
                  {i.ticketCount ? ` · ${plural(i.ticketCount, "linked ticket")}` : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}
