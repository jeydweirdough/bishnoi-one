// One incident: where it is, what people have been told, and the tickets
// that came in about it.
import Link from "next/link";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { IncidentSeverityMark, IncidentStatusMark, SeverityMark, TicketStatusMark } from "@/src/components/marks";
import { EditIncident, PostUpdate } from "@/src/components/incidents/incident-forms";
import { reach, span } from "@/src/components/incidents/words";
import type { IncidentDetail, IncidentStatus, Options } from "@/src/lib/types";
import { INCIDENT_KINDS, INCIDENT_STATUSES, ago, when } from "@/src/lib/words";

type Params = Promise<{ id: string }>;

const getIncident = (id: string) => load<{ incident: IncidentDetail }>(`/platform/incidents/${enc(id)}`).then((b) => b.incident);

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    const i = await getIncident(id);
    return { title: `${i.number} ${i.title}` };
  } catch {
    return { title: "Incident" };
  }
}

/** Investigating → Identified → Monitoring → Resolved, each with what it means, and where this one is. */
function Stepper({ status }: { status: IncidentStatus }) {
  const steps = Object.keys(INCIDENT_STATUSES) as IncidentStatus[];
  const at = steps.indexOf(status);
  return (
    <ol aria-label="Where it is" className="grid gap-px overflow-hidden rounded-[3px] bg-rule sm:grid-cols-4">
      {steps.map((s, n) => (
        <li
          key={s}
          aria-current={n === at ? "step" : undefined}
          className={`px-4 py-3 ${n === at ? "bg-hema text-white" : "bg-sheet"}`}
        >
          <p className={`text-sm font-semibold ${n === at ? "" : n < at ? "text-hema" : "text-ink-3"}`}>
            <span aria-hidden className="mr-1.5 tabular-nums">{n + 1}.</span>
            {INCIDENT_STATUSES[s].label}
            {n < at && <span className="sr-only"> (done)</span>}
            {n === at && <span className="sr-only"> (now)</span>}
          </p>
          <p className={`mt-0.5 text-meta ${n === at ? "text-white/85" : "text-ink-3"}`}>{INCIDENT_STATUSES[s].what}</p>
        </li>
      ))}
    </ol>
  );
}

export default async function IncidentPage({ params }: { params: Params }) {
  const { id } = await params;
  const [incident, options] = await Promise.all([getIncident(id), load<Options>("/platform/options")]);

  return (
    <>
      <PageHeader
        crumbs={[{ href: incident.isActive ? "/incidents" : "/incidents?state=resolved", label: "Incidents" }]}
        title={`${incident.number} ${incident.title}`}
        // Changing what it says about itself acts on the incident, so it sits with its name.
        tools={<EditIncident incident={incident} options={options} />}
        actions={<PostUpdate incident={incident} />}
      >
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <IncidentSeverityMark severity={incident.severity} />
          <IncidentStatusMark status={incident.status} />
          <span className="text-meta">
            {INCIDENT_KINDS[incident.kind]} ·{" "}
            {incident.resolvedAt ? `lasted ${span(incident.startedAt, incident.resolvedAt)}` : `going on for ${span(incident.startedAt, null)}`}
          </span>
        </span>
      </PageHeader>

      <div className="mb-5">
        <Stepper status={incident.status} />
        <p className="mt-2 text-meta text-ink-3">It moves on when someone posts an update saying where it is now.</p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <Sheet className="px-5 pt-4 pb-2">
          <SectionTitle icon="history">Updates</SectionTitle>
          {incident.updates.length === 0 ? (
            <Empty icon="history" title="No updates yet.">
              Post one to tell the people it reaches what&apos;s happening.
            </Empty>
          ) : (
            <ol className="mt-1 divide-y divide-rule">
              {incident.updates.map((u) => (
                <li key={u.id} className="py-3">
                  <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <IncidentStatusMark status={u.status} />
                    <span className="text-meta text-ink-3">
                      {u.author} ·{" "}
                      <time dateTime={u.createdAt} title={when(u.createdAt)}>
                        {ago(u.createdAt)}
                      </time>
                    </span>
                  </p>
                  <p className="mt-1 text-sm whitespace-pre-line text-ink">{u.body}</p>
                </li>
              ))}
            </ol>
          )}
        </Sheet>

        <div className="space-y-5">
          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle icon="particulars">Details</SectionTitle>
            <div className="mt-3">
              <Particulars
                items={[
                  [
                    "Application",
                    incident.application ? (
                      <Link href={`/applications/${incident.application.id}`} className="text-hema hover:underline">
                        {incident.application.name}
                      </Link>
                    ) : (
                      "The whole platform"
                    ),
                  ],
                  [
                    "Reaches",
                    incident.companies.length > 0 ? (
                      <span>
                        {incident.companies.map((c, n) => (
                          <span key={c.id}>
                            {n > 0 && ", "}
                            <Link href={`/companies/${c.id}`} className="text-hema hover:underline">
                              {c.name}
                            </Link>
                          </span>
                        ))}
                      </span>
                    ) : (
                      reach(incident)
                    ),
                  ],
                  ["Lead", incident.lead?.name ?? "Nobody yet"],
                  ["Started", when(incident.startedAt)],
                  ["Resolved", incident.resolvedAt ? when(incident.resolvedAt) : "Not yet"],
                  ["Declared by", incident.createdBy],
                ]}
              />
              {incident.summary && <p className="mt-4 border-t border-rule pt-3 text-sm whitespace-pre-line text-ink-2">{incident.summary}</p>}
            </div>
          </Sheet>

          <Sheet className="px-5 pt-4 pb-3">
            <SectionTitle icon="support">Linked tickets</SectionTitle>
            {incident.tickets.length === 0 ? (
              <p className="py-2 text-meta text-ink-3">None yet. Link a ticket to this incident from the ticket&apos;s page, beside Incident.</p>
            ) : (
              <ul className="mt-1 divide-y divide-rule">
                {incident.tickets.map((t) => (
                  <li key={t.id} className="py-2.5">
                    <p>
                      <Link href={`/support/${t.id}`} className="font-semibold text-hema hover:underline">
                        {t.number}
                      </Link>{" "}
                      <span className="text-sm">{t.title}</span>
                    </p>
                    <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                      <SeverityMark severity={t.severity} />
                      <TicketStatusMark status={t.status} />
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Sheet>
        </div>
      </div>
    </>
  );
}
