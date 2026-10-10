// One application: whether it's working and why, who uses it, what was
// deployed, what it connects to, and what's gone wrong with it.
import Link from "next/link";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { DeleteRecord } from "@/src/components/delete-record";
import { getStaff } from "@/src/components/gate";
import { ActivityList } from "@/src/components/activity-list";
import { HealthMark, IncidentSeverityMark, IncidentStatusMark, KindMark, SeverityMark, Tabs, TicketStatusMark } from "@/src/components/marks";
import { BackToCheck, DeclareStatus, EditApplication, RetireApplication } from "@/src/components/applications/application-forms";
import { AddIntegration, EditIntegration, RecordDeployment, RemoveIntegration } from "@/src/components/applications/deployment-forms";
import { CheckStrip } from "@/src/components/applications/check-strip";
import { EnvironmentMark } from "@/src/components/applications/marks";
import { checkLine, uptimeText } from "@/src/components/applications/words";
import { AnswerGauge, UptimeGauge } from "@/src/components/health-gauges";
import type { ApplicationDetail, AuditEntry } from "@/src/lib/types";
import { HEALTH, ago, plural, when } from "@/src/lib/words";

type Params = Promise<{ id: string }>;
type Search = Promise<Record<string, string | string[] | undefined>>;

const getApp = (id: string) => load<{ application: ApplicationDetail }>(`/platform/applications/${enc(id)}`).then((b) => b.application);

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    return { title: (await getApp(id)).name };
  } catch {
    return { title: "Application" };
  }
}

const TABS = ["overview", "companies", "deployments", "integrations", "issues", "activity"] as const;
type Tab = (typeof TABS)[number];

const DECLARED = { maintenance: "Maintenance", degraded: "Degraded", outage: "Outage" } as const;

export default async function ApplicationPage({ params, searchParams }: { params: Params; searchParams: Search }) {
  const { id } = await params;
  const asked = (await searchParams).tab;
  const tab: Tab = TABS.find((t) => t === asked) ?? "overview";
  const [app, staff] = await Promise.all([getApp(id), getStaff()]);
  const admin = staff.canAdminister;
  const activeIncidents = app.incidents.filter((i) => i.status !== "resolved").length;
  const base = `/applications/${app.id}`;

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/applications", label: "Applications" }]}
        title={
          <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1">
            {app.name}
            <HealthMark status={app.status} />
          </span>
        }
        // Changing its details and retiring it act on the application itself, so they sit with its name.
        tools={
          admin && (
            <>
              <EditApplication app={app} />
              <RetireApplication app={app} />
              <DeleteRecord
                kind="application"
                id={app.id}
                name={app.name}
                after="/applications"
                done="Application deleted"
                body={`${app.name} goes from the registry, with its deployments, integrations and links. Only once no company has it: the applications sign in through it. To keep its history, retire it instead.`}
              />
            </>
          )
        }
        actions={admin && app.isActive && <DeclareStatus app={app} />}
      >
        {app.no && <span className="text-meta tabular-nums">No. {app.no} · </span>}
        <span className="font-mono text-meta">{app.key}</span>
        {app.version && <span> · version {app.version}</span>}
        {!app.isActive && <span> · retired, so not checked</span>}
      </PageHeader>

      {app.statusOverride && (
        <div role="status" className="mb-5 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-[18px] border border-rule-strong bg-sheet px-4 py-3 text-sm">
          <p>
            <b className="font-semibold">Declared: {DECLARED[app.statusOverride]}.</b>{" "}
            {app.statusNote && <span className="text-ink-2">{app.statusNote} </span>}
            <span className="text-ink-3">Every screen shows this over what the health check says.</span>
          </p>
          {admin && <BackToCheck app={app} />}
        </div>
      )}

      <Tabs
        current={tab}
        tabs={[
          { key: "overview", label: "Overview", href: base },
          { key: "companies", label: "Companies", href: `${base}?tab=companies`, count: app.companies.length },
          { key: "deployments", label: "Deployments", href: `${base}?tab=deployments`, count: app.deployments.length },
          { key: "integrations", label: "Integrations", href: `${base}?tab=integrations`, count: app.integrations.length },
          { key: "issues", label: "Issues", href: `${base}?tab=issues`, count: app.openTickets.length + activeIncidents },
          { key: "activity", label: "Activity", href: `${base}?tab=activity` },
        ]}
      />

      {tab === "overview" && <Overview app={app} />}
      {tab === "companies" && <Companies app={app} />}
      {tab === "deployments" && <Deployments app={app} admin={admin} />}
      {tab === "integrations" && <Integrations app={app} admin={admin} />}
      {tab === "issues" && <Issues app={app} />}
      {tab === "activity" && <Activity app={app} />}
    </>
  );
}

function Overview({ app }: { app: ApplicationDetail }) {
  const monitored = Boolean(app.healthUrl);
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-start">
      <Sheet className="px-5 pt-4 pb-5">
        <SectionTitle icon="particulars">About it</SectionTitle>
        <div className="mt-3">
          <Particulars
            items={[
              ["What it's for", app.description],
              [
                "Where people open it",
                app.appUrl ? (
                  <a href={app.appUrl} target="_blank" rel="noopener noreferrer" className="text-hema hover:underline">
                    {app.appUrl.replace(/^https?:\/\//, "")}
                  </a>
                ) : null,
              ],
              ["Its API", app.apiUrl ? <span className="font-mono text-meta break-all">{app.apiUrl}</span> : "None, so no other application can use it"],
              [
                "Connected",
                <Link key="c" href="/connections" className="text-hema hover:underline">
                  {app.connected ? (app.connectedAt ? `Yes, asked ${ago(app.connectedAt)}` : "Key made, not connected yet") : "No"}
                </Link>,
              ],
              ["Health address", app.healthUrl ? <span className="font-mono text-meta break-all">{app.healthUrl}</span> : "None, so it isn't checked"],
              ["Version", app.version],
              ["Users", plural(app.userCount, "person", "people")],
              ["Registered", when(app.createdAt)],
            ]}
          />
        </div>
      </Sheet>

      <Sheet className="px-5 pt-4 pb-5">
        <SectionTitle icon="monitoring">Health</SectionTitle>
        <div className="mt-3 space-y-4">
          {monitored && app.isActive && (
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <UptimeGauge value={app.uptime} />
              <AnswerGauge value={app.lastCheck?.ms ?? null} slowMs={app.slowMs ?? 1500} label="Last answer" />
            </div>
          )}
          <Particulars
            items={[
              ["Now", <HealthMark key="s" status={app.status} />],
              ["Last check", app.isActive ? checkLine(app.lastCheck, monitored) : "Retired, so not checked."],
              ["Up, last 24 h", uptimeText(app.uptime)],
            ]}
          />
          <CheckStrip checks={app.history} />
          <p className="text-meta text-ink-3">
            The platform asks the health address when someone opens a screen and the last answer is out of date. A slow answer counts as degraded; no answer, or an error, as down.
          </p>
        </div>
      </Sheet>
    </div>
  );
}

function Companies({ app }: { app: ApplicationDetail }) {
  return (
    <Sheet className="overflow-hidden">
      {app.companies.length === 0 ? (
        <Empty icon="companies" title="No company has it yet.">
          Give it to a company from that company&apos;s page; then its people can be given access.
        </Empty>
      ) : (
        <ul className="divide-y divide-rule">
          {app.companies.map((c) => (
            <li key={c.id} className="flex items-baseline justify-between gap-4 px-5 py-3">
              <span className="min-w-0">
                <Link href={`/companies/${c.id}`} className="font-semibold text-hema hover:underline">
                  {c.name}
                </Link>
                {c.status === "suspended" && <span className="ml-2 text-stamp text-ink-3 uppercase">Suspended</span>}
              </span>
              <span className="shrink-0 text-meta text-ink-2">{plural(c.userCount, "user")}</span>
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}

function Deployments({ app, admin }: { app: ApplicationDetail; admin: boolean }) {
  return (
    <Sheet className="px-5 pt-4 pb-2">
      <SectionTitle icon="history" action={admin && <RecordDeployment appId={app.id} appName={app.name} />}>
        Deployments
      </SectionTitle>
      {app.deployments.length === 0 ? (
        <Empty icon="history" title="No deployments recorded.">
          {admin ? "Record one when a release goes out. One to production sets the version people are on." : "A Platform Admin records them as releases go out."}
        </Empty>
      ) : (
        <ul className="mt-1 divide-y divide-rule">
          {app.deployments.map((d) => (
            <li key={d.id} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 py-3">
              <div className="min-w-0">
                <p className="font-semibold tabular-nums">
                  {d.version}
                  {d.environment === "production" && d.version === app.version && <span className="ml-2 text-meta font-normal text-ink-3">live now</span>}
                </p>
                {d.notes && <p className="mt-0.5 text-sm whitespace-pre-line text-ink-2">{d.notes}</p>}
                <p className="text-meta text-ink-3">Recorded by {d.recordedBy}</p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                <EnvironmentMark environment={d.environment} />
                <time dateTime={d.deployedAt} title={when(d.deployedAt)} className="text-meta text-ink-3">
                  {ago(d.deployedAt)}
                </time>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}

function Integrations({ app, admin }: { app: ApplicationDetail; admin: boolean }) {
  return (
    <Sheet className="px-5 pt-4 pb-2">
      <SectionTitle icon="teams" action={admin && <AddIntegration appId={app.id} appName={app.name} />}>
        Integrations
      </SectionTitle>
      {app.integrations.length === 0 ? (
        <Empty icon="teams" title="Nothing recorded that it connects to.">
          {admin ? "Add its payments, messaging or other systems, so their state sits with the application's." : "A Platform Admin records them."}
        </Empty>
      ) : (
        <ul className="mt-1 divide-y divide-rule">
          {app.integrations.map((i) => (
            <li key={i.id} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 py-3">
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="font-semibold">{i.name}</span>
                  <HealthMark status={i.status} label={HEALTH[i.status]} />
                </p>
                <p className="text-meta text-ink-3">
                  {[i.target, i.healthUrl ? `Checked automatically. ${checkLine(i.lastCheck, true)}` : "Status set by hand"].filter(Boolean).join(" · ")}
                </p>
                {i.notes && <p className="mt-0.5 text-sm whitespace-pre-line text-ink-2">{i.notes}</p>}
              </div>
              {admin && (
                <span className="flex shrink-0 items-center">
                  <EditIntegration link={i} />
                  <RemoveIntegration link={i} />
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}

function Issues({ app }: { app: ApplicationDetail }) {
  return (
    <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
      <Sheet className="px-5 pt-4 pb-2">
        <SectionTitle
          icon="support"
          action={
            <Link href={`/support?application=${app.id}&state=all`} className="text-meta text-hema hover:underline">
              All its tickets
            </Link>
          }
        >
          Open tickets
        </SectionTitle>
        {app.openTickets.length === 0 ? (
          <Empty icon="support" title="No open tickets.">
            Complaints, bugs and requests about {app.name} show up here once they&apos;re logged in Support.
          </Empty>
        ) : (
          <ul className="mt-1 divide-y divide-rule">
            {app.openTickets.map((t) => (
              <li key={t.id} className="py-2.5">
                <p className="flex flex-wrap items-baseline gap-x-2">
                  <Link href={`/support/${t.id}`} className="font-semibold text-hema hover:underline">
                    {t.number}
                  </Link>
                  <span className="min-w-0">{t.title}</span>
                </p>
                <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                  <KindMark kind={t.kind} />
                  <SeverityMark severity={t.severity} />
                  <TicketStatusMark status={t.status} />
                  <time dateTime={t.createdAt} title={when(t.createdAt)} className="text-meta text-ink-3">
                    {ago(t.createdAt)}
                  </time>
                </p>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
      <Sheet className="px-5 pt-4 pb-2">
        <SectionTitle icon="incidents">Incidents</SectionTitle>
        {app.incidents.length === 0 ? (
          <Empty icon="incidents" title="No incidents.">
            When {app.name} breaks for many people at once, declare an incident from Incidents.
          </Empty>
        ) : (
          <ul className="mt-1 divide-y divide-rule">
            {app.incidents.map((i) => (
              <li key={i.id} className="py-2.5">
                <p className="flex flex-wrap items-baseline gap-x-2">
                  <Link href={`/incidents/${i.id}`} className="font-semibold text-hema hover:underline">
                    {i.number}
                  </Link>
                  <span className="min-w-0">{i.title}</span>
                </p>
                <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                  <IncidentSeverityMark severity={i.severity} />
                  <IncidentStatusMark status={i.status} />
                  <span className="text-meta text-ink-3">
                    {i.resolvedAt ? `resolved ${ago(i.resolvedAt)}` : `started ${ago(i.startedAt)}`}
                  </span>
                </p>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </div>
  );
}

async function Activity({ app }: { app: ApplicationDetail }) {
  const { entries } = await load<{ entries: AuditEntry[] }>(`/platform/activity?application_id=${enc(app.id)}`);
  return (
    <Sheet className="px-5 pt-4 pb-2">
      <SectionTitle icon="auditLog">Activity</SectionTitle>
      <ActivityList entries={entries} showCategory empty={`Nothing done to ${app.name} yet.`} />
    </Sheet>
  );
}
