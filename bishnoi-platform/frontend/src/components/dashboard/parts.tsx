import Link from "next/link";
import { HealthGauges } from "../health-gauges";
import type { ReactNode } from "react";
import { Flag } from "@/src/platform/ui/marks";
import { Empty, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { HealthMark, IncidentSeverityMark, IncidentStatusMark, SeverityMark } from "../marks";
import { NoticeLevelMark, NoticeStateMark, audience, noticeWindow } from "../communications/notice-words";
import { INCIDENT_KINDS, NOTICE_KINDS, TICKET_KINDS, ago, plural } from "../../lib/words";
import type { Dashboard, Health } from "../../lib/types";

// The dashboard's sheets. Each answers one question about the platform right
// now, and each links to the page where it can be worked on.

const linkClass = "text-meta font-semibold text-hema hover:underline";

function SeeAll({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className={linkClass}>
      {children}
    </Link>
  );
}

/** The six counts across the top: each one a way into its page. */
export function Counts({ counts }: { counts: Dashboard["counts"] }) {
  const tiles: { label: string; value: number; note?: string; href: string; flag?: boolean }[] = [
    { label: "Companies", value: counts.activeCompanies, note: `active of ${counts.companies.toLocaleString("en-PH")}`, href: "/companies" },
    { label: "Users", value: counts.activeUsers, note: `active of ${counts.users.toLocaleString("en-PH")}`, href: "/users" },
    { label: "Applications", value: counts.applications, note: "active", href: "/applications" },
    { label: "Open issues", value: counts.openTickets, note: "tickets not yet resolved", href: "/support" },
    { label: "Incidents", value: counts.activeIncidents, note: "active now", href: "/incidents", flag: true },
    { label: "Access requests", value: counts.pendingRequests, note: "pending decision", href: "/access" },
  ];
  return (
    <Sheet className="mb-5 overflow-hidden">
      {/* A 1px gap over the rule colour draws the hairlines between tiles at every width. */}
      <div className="grid grid-cols-2 gap-px bg-rule sm:grid-cols-3 xl:grid-cols-6 [&>*]:bg-sheet">
        {tiles.map((t) => (
          <Link key={t.label} href={t.href} className="group block min-w-0 px-5 py-4">
            <span className="block text-figure text-ink group-hover:text-hema">{t.value.toLocaleString("en-PH")}</span>
            <span className="mt-0.5 block text-meta font-medium text-ink-2">
              {t.flag && t.value > 0 ? <Flag letter="!">{t.label}</Flag> : t.label}
            </span>
            {t.note && <span className="block text-meta text-ink-3">{t.note}</span>}
          </Link>
        ))}
      </div>
    </Sheet>
  );
}

/** Incidents still open, worst first as the API gives them. */
export function ActiveIncidents({ incidents }: { incidents: Dashboard["incidents"] }) {
  return (
    <Sheet className="px-5 pt-4 pb-3">
      <SectionTitle icon="incidents" action={<SeeAll href="/incidents">All incidents</SeeAll>}>
        Active incidents
      </SectionTitle>
      {incidents.length === 0 ? (
        <p className="py-3 text-sm text-ink-3">No active incidents. When something breaks for many people, declare one on Incidents.</p>
      ) : (
        <ul className="divide-y divide-rule" role="list">
          {incidents.map((i) => (
            <li key={i.id} className="py-2.5">
              <Link href={`/incidents/${i.id}`} className="group block">
                <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                  <IncidentSeverityMark severity={i.severity} />
                  <IncidentStatusMark status={i.status} />
                  <span className="text-meta text-ink-3">{i.number}</span>
                </span>
                <span className="mt-1 block text-sm font-semibold text-ink group-hover:text-hema">{i.title}</span>
                <span className="block text-meta text-ink-3">
                  {INCIDENT_KINDS[i.kind]}
                  {i.application && ` · ${i.application.name}`}
                  {i.companies.length > 0 && ` · ${plural(i.companies.length, "company", "companies")}`} · started {ago(i.startedAt)}
                  {i.lead ? ` · led by ${i.lead.name}` : " · nobody leading it yet"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}

const OVERALL: Record<Dashboard["health"]["overall"], string> = {
  operational: "All systems operational",
  degraded: "Some services degraded",
  down: "Service outage",
};

function HealthRow({ name, status, ms, note, href }: { name: string; status: Health; ms?: number | null; note?: string | null; href?: string }) {
  return (
    <li className="flex items-baseline justify-between gap-3 py-2">
      <span className="min-w-0 text-sm">
        {href ? (
          <Link href={href} className="text-ink hover:text-hema hover:underline">
            {name}
          </Link>
        ) : (
          <span className="text-ink">{name}</span>
        )}
        {note && <span className="block text-meta text-ink-3">{note}</span>}
      </span>
      <span className="flex shrink-0 items-baseline gap-2">
        <HealthMark status={status} />
        <span className="w-14 text-right text-meta text-ink-3 tabular-nums">{ms == null ? "—" : `${ms.toLocaleString("en-PH")} ms`}</span>
      </span>
    </li>
  );
}

/** Whether the platform and each application answer, and how fast. */
export function SystemHealth({ health }: { health: Dashboard["health"] }) {
  // Anything not running comes first, so a problem is never below the fold of the list.
  const order: Record<Health, number> = { down: 0, degraded: 1, maintenance: 2, unknown: 3, operational: 4, retired: 5 };
  const apps = [...health.applications].sort((a, b) => order[a.status] - order[b.status]);
  return (
    <Sheet className="px-5 pt-4 pb-3">
      <SectionTitle icon="monitoring" action={<SeeAll href="/monitoring">Monitoring</SeeAll>}>
        System health
      </SectionTitle>
      <p className="mt-1 flex flex-wrap items-baseline gap-x-2 text-sm">
        <HealthMark status={health.overall} label={OVERALL[health.overall]} />
        <span className="text-meta text-ink-3">checked {ago(health.checkedAt)}</span>
      </p>
      <div className="mt-4 mb-2">
        <HealthGauges health={health} />
      </div>
      <ul className="mt-1 divide-y divide-rule" role="list">
        <HealthRow
          name="Platform API"
          status={health.platformApi.status}
          ms={health.platformApi.averageMs}
          note={health.platformApi.failedPercent > 0 ? `${health.platformApi.failedPercent}% of requests failed` : null}
        />
        <HealthRow name="Database" status={health.database.status} ms={health.database.ms} note={health.database.detail} />
        {apps.map((a) => (
          <HealthRow
            key={a.id}
            name={a.name}
            status={a.status}
            ms={a.lastCheck?.ms}
            note={a.statusNote ?? (a.monitored ? null : "Not monitored: no health check URL")}
            href={`/applications/${a.id}`}
          />
        ))}
      </ul>
      {apps.length === 0 && <p className="py-2 text-meta text-ink-3">No applications registered yet. Register one under Applications to monitor it here.</p>}
    </Sheet>
  );
}

/** The Platform API's own traffic over the last hour. */
export function Traffic({ traffic }: { traffic: Dashboard["traffic"] }) {
  const figures: [string, string][] = [
    ["Requests per minute", traffic.requestsPerMinute.toLocaleString("en-PH")],
    ["Staff signed in", traffic.activeSessions.toLocaleString("en-PH")],
    ["Failed requests", `${traffic.failedPercent}%`],
    ["Average response time", traffic.averageMs == null ? "—" : `${traffic.averageMs.toLocaleString("en-PH")} ms`],
  ];
  return (
    <Sheet className="px-5 pt-4 pb-4">
      <SectionTitle icon="activity" action={<SeeAll href="/monitoring?tab=traffic">Traffic</SeeAll>}>
        Traffic
      </SectionTitle>
      <p className="text-meta text-ink-3">
        The Platform API&apos;s own requests over the last hour (per minute over the last five). The applications count theirs on their own.
      </p>
      <dl className="mt-3 grid grid-cols-2 gap-x-5 gap-y-3">
        {figures.map(([label, value]) => (
          <div key={label}>
            <dt className="text-meta text-ink-3">{label}</dt>
            <dd className="text-heading text-ink tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </Sheet>
  );
}

/** Open tickets by kind, and the ones past their response target. */
export function SupportSummary({ support, overdue }: { support: Dashboard["support"]; overdue: Dashboard["overdue"] }) {
  const rows: { label: string; value: number; href: string; flag?: boolean }[] = [
    { label: "Critical bugs", value: support.criticalBugs, href: "/support?kind=bug&severity=critical", flag: true },
    { label: TICKET_KINDS.bug.many, value: support.bugs, href: "/support?kind=bug" },
    { label: TICKET_KINDS.complaint.many, value: support.complaints, href: "/support?kind=complaint" },
    { label: TICKET_KINDS.issue.many, value: support.issues, href: "/support?kind=issue" },
    { label: TICKET_KINDS.feature.many, value: support.features, href: "/support?kind=feature" },
    { label: TICKET_KINDS.support.many, value: support.support, href: "/support?kind=support" },
    { label: "Unassigned", value: support.unassigned, href: "/support?assignee=none" },
    { label: "Overdue", value: support.overdue, href: "/support", flag: true },
  ];
  return (
    <Sheet className="px-5 pt-4 pb-3">
      <SectionTitle icon="support" action={<SeeAll href="/support">All tickets</SeeAll>}>
        Support
      </SectionTitle>
      <p className="text-meta text-ink-3">Open tickets: reported and not yet resolved.</p>
      <ul className="mt-1 grid gap-x-6 sm:grid-cols-2" role="list">
        {rows.map((r) => (
          <li key={r.label} className="border-b border-rule">
            <Link href={r.href} className="group flex items-baseline justify-between gap-3 py-2 text-sm">
              <span className="text-ink-2 group-hover:text-hema">{r.flag && r.value > 0 ? <Flag letter="!">{r.label}</Flag> : r.label}</span>
              <span className={`tabular-nums ${r.value > 0 ? "font-semibold text-ink" : "text-ink-3"}`}>{r.value.toLocaleString("en-PH")}</span>
            </Link>
          </li>
        ))}
      </ul>

      <h3 className="mt-4 text-sm font-semibold text-ink">Overdue tickets</h3>
      {overdue.length === 0 ? (
        <p className="py-2 text-meta text-ink-3">No overdue tickets. Every open ticket is within its response target (Settings, Notifications).</p>
      ) : (
        <ul className="divide-y divide-rule" role="list">
          {overdue.map((t) => {
            const late = ago(t.dueAt);
            return (
              <li key={t.id} className="py-2">
                <Link href={`/support/${t.id}`} className="group flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                  <span className="text-meta text-ink-3">{t.number}</span>
                  <span className="min-w-0 flex-1 text-sm text-ink group-hover:text-hema">{t.title}</span>
                  <SeverityMark severity={t.severity} />
                  <span className="text-meta text-ink-2">overdue {late === "just now" ? "since just now" : `by ${late.replace(" ago", "")}`}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Sheet>
  );
}

/** Published notices showing now or coming up; maintenance first. */
export function Notices({ notices }: { notices: Dashboard["notices"] }) {
  const sorted = [...notices].sort((a, b) => Number(b.kind === "maintenance") - Number(a.kind === "maintenance"));
  return (
    <Sheet className="px-5 pt-4 pb-3">
      <SectionTitle icon="communications" action={<SeeAll href="/communications">Communications</SeeAll>}>
        Notices
      </SectionTitle>
      {sorted.length === 0 ? (
        <Empty title="No active or scheduled notices" icon="communications">
          Announce maintenance or news on Communications, and the applications show it to their users.
        </Empty>
      ) : (
        <ul className="divide-y divide-rule" role="list">
          {sorted.map((n) => (
            <li key={n.id} className="py-2.5">
              <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                <NoticeStateMark state={n.state} />
                <NoticeLevelMark level={n.level} />
                <span className="text-meta text-ink-3">{NOTICE_KINDS[n.kind].one}</span>
              </span>
              <Link href={`/communications?kind=${n.kind}`} className="mt-1 block text-sm font-semibold text-ink hover:text-hema">
                {n.title}
              </Link>
              <span className="block text-meta text-ink-3">
                {audience(n)} · {noticeWindow(n)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}

