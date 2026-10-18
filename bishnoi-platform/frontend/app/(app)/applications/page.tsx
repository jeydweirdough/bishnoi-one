// Applications: every app on the platform, whether it's working, what was
// deployed and what each connects to.
import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { Pill } from "@/src/platform/ui/figures";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { load } from "@/src/platform/lib/api";
import { DeleteRecord } from "@/src/components/delete-record";
import { getStaff } from "@/src/components/gate";
import { HealthMark, Tabs } from "@/src/components/marks";
import { RegisterApplication } from "@/src/components/applications/application-forms";
import { EnvironmentMark } from "@/src/components/applications/marks";
import { checkLine, uptimeText } from "@/src/components/applications/words";
import type { Application, Deployment, Integration } from "@/src/lib/types";
import { HEALTH, ago, plural, when } from "@/src/lib/words";

export const metadata = { title: "Applications" };

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

const TABS = [
  { key: "registry", label: "Registry" },
  { key: "deployments", label: "Deployments" },
  { key: "integrations", label: "Integrations" },
] as const;

export default async function ApplicationsPage({ searchParams }: { searchParams: Search }) {
  const params = await searchParams;
  const tab = TABS.find((t) => t.key === one(params.tab))?.key ?? "registry";
  const retired = one(params.retired) === "1";
  const staff = await getStaff();

  return (
    <>
      <PageHeader title="Applications" actions={staff.canAdminister && <RegisterApplication />}>
        Every application on the platform. The platform asks each one&apos;s health address itself whether it&apos;s up, so nobody has to report it.
      </PageHeader>
      <Tabs current={tab} tabs={TABS.map((t) => ({ ...t, href: t.key === "registry" ? "/applications" : `/applications?tab=${t.key}` }))} />
      {tab === "registry" && <Registry retired={retired} canAdminister={staff.canAdminister} />}
      {tab === "deployments" && <Deployments canDelete={staff.canAdminister} />}
      {tab === "integrations" && <Integrations />}
    </>
  );
}

// What needs attention comes first and stands apart (the Von Restorff effect);
// each row says only what answers "is it fine?" (Hick's law): its state, uptime
// and answer time, with what it's used by on one small line and problems only
// when there are some; things that belong together sit together (proximity);
// and the whole row opens the application, a big target (Fitts's law).
const NEEDS: Record<Application["status"], boolean> = { down: true, degraded: true, maintenance: true, unknown: true, operational: false, retired: false };
const ORDER: Record<Application["status"], number> = { down: 0, degraded: 1, maintenance: 2, unknown: 3, operational: 4, retired: 5 };

function uptimeTone(uptime: number | null | undefined): string {
  if (uptime == null) return "text-ink-3";
  return uptime >= 99 ? "text-sage-deep" : uptime >= 95 ? "text-due-today" : "text-danger";
}

function AppRow({ a }: { a: Application }) {
  const attention = NEEDS[a.status] && a.isActive;
  const problems = [
    a.activeIncidents ? `${a.activeIncidents} incident${a.activeIncidents === 1 ? "" : "s"} now` : null,
    a.openTickets ? `${a.openTickets} open ticket${a.openTickets === 1 ? "" : "s"}` : null,
  ].filter(Boolean) as string[];
  const ms = a.lastCheck?.ms;
  return (
    <li>
      <Link
        href={`/applications/${a.id}`}
        className={`group grid gap-x-6 gap-y-2 px-5 py-4 transition-colors hover:bg-mint focus-visible:bg-mint focus-visible:outline-none sm:grid-cols-[minmax(0,1fr)_auto] ${
          attention ? "border-l-4 border-danger bg-danger-tint/40" : "border-l-4 border-transparent"
        }`}
      >
        <span className="min-w-0">
          <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="text-base font-semibold text-ink group-hover:underline">{a.name}</span>
            <HealthMark status={a.status} />
            {problems.map((p) => (
              <Pill key={p} tone="bad">
                {p}
              </Pill>
            ))}
          </span>
          <span className="mt-0.5 block truncate text-meta text-ink-2">
            {a.statusNote && <span className="text-ink">{a.statusNote} · </span>}
            {a.isActive ? checkLine(a.lastCheck, Boolean(a.healthUrl)) : "Retired: not monitored."}
          </span>
          <span className="mt-1 block text-meta text-ink-3">
            <span className="font-mono">{a.key}</span>
            {a.no ? ` · No. ${a.no}` : ""} · {plural(a.companyCount ?? 0, "company", "companies")} · {plural(a.userCount ?? 0, "user")}
            {a.version ? ` · version ${a.version}` : ""}
          </span>
        </span>
        <span className="flex items-center gap-6 sm:justify-end">
          <span className="text-right">
            <span className={`block text-lg font-semibold tabular-nums ${uptimeTone(a.uptime)}`}>{uptimeText(a.uptime)}</span>
            <span className="block text-meta text-ink-3">uptime, 24 h</span>
          </span>
          <span className="w-20 text-right">
            <span className="block text-lg font-semibold text-ink tabular-nums">{ms == null ? "—" : ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`}</span>
            <span className="block text-meta text-ink-3">last response</span>
          </span>
          <ChevronRight className="hidden size-4 text-ink-3 group-hover:text-ink sm:block" aria-hidden />
        </span>
      </Link>
    </li>
  );
}

async function Registry({ retired, canAdminister }: { retired: boolean; canAdminister: boolean }) {
  const { applications } = await load<{ applications: Application[] }>(`/platform/applications${retired ? "?retired=true" : ""}`);
  const sorted = [...applications].sort((x, y) => ORDER[x.status] - ORDER[y.status] || x.name.localeCompare(y.name));
  const attention = sorted.filter((a) => NEEDS[a.status] && a.isActive);
  const running = sorted.filter((a) => !(NEEDS[a.status] && a.isActive));
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="flex flex-wrap items-center gap-2 text-sm text-ink-2" role="status">
          {applications.length === 0 ? null : attention.length > 0 ? (
            <>
              <Pill tone="bad">{attention.length} need attention</Pill>
              <span>
                {running.length} running{retired ? ", or retired" : ""}
              </span>
            </>
          ) : (
            <Pill tone="good">All {applications.length} running</Pill>
          )}
        </p>
        <ToggleLinks
          current={retired ? "all" : "active"}
          options={[
            { value: "active", label: "Active", href: "/applications" },
            { value: "all", label: "Include retired", href: "/applications?retired=1" },
          ]}
        />
      </div>
      {applications.length === 0 ? (
        <Sheet>
          <Empty icon="apps" title="No applications yet.">
            {canAdminister ? "Register one with its health address, and the platform starts checking it." : "A Platform Admin registers them."}
          </Empty>
        </Sheet>
      ) : (
        <div className="space-y-6">
          {attention.length > 0 && (
            <section aria-labelledby="needs-attention">
              <h2 id="needs-attention" className="mb-2 text-caps text-danger uppercase">
                Needs attention
              </h2>
              <Sheet className="overflow-hidden">
                <ul className="divide-y divide-rule">{attention.map((a) => <AppRow key={a.id} a={a} />)}</ul>
              </Sheet>
            </section>
          )}
          {running.length > 0 && (
            <section aria-labelledby="running">
              <h2 id="running" className="mb-2 text-caps text-ink-3 uppercase">
                {retired ? "Active and retired" : "Active"}
              </h2>
              <Sheet className="overflow-hidden">
                <ul className="divide-y divide-rule">{running.map((a) => <AppRow key={a.id} a={a} />)}</ul>
              </Sheet>
            </section>
          )}
        </div>
      )}
    </>
  );
}

async function Deployments({ canDelete }: { canDelete: boolean }) {
  const { deployments } = await load<{ deployments: Deployment[] }>("/platform/deployments");
  return (
    <Sheet className="overflow-hidden">
      {deployments.length === 0 ? (
        <Empty icon="history" title="No deployments recorded yet.">
          Open an application and use Record a deployment when a release goes out.
        </Empty>
      ) : (
        <ul className="divide-y divide-rule">
          {deployments.map((d) => (
            <li key={d.id} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 px-5 py-3">
              <div className="min-w-0">
                <p>
                  <Link href={`/applications/${d.applicationId}?tab=deployments`} className="font-semibold text-hema hover:underline">
                    {d.applicationName}
                  </Link>{" "}
                  <span className="font-semibold tabular-nums">{d.version}</span>
                </p>
                {d.notes && <p className="mt-0.5 text-sm whitespace-pre-line text-ink-2">{d.notes}</p>}
                <p className="text-meta text-ink-3">Recorded by {d.recordedBy}</p>
              </div>
              <div className="flex shrink-0 items-start gap-2">
                <div className="flex flex-col items-end gap-1">
                  <EnvironmentMark environment={d.environment} />
                  <time dateTime={d.deployedAt} title={when(d.deployedAt)} className="text-meta text-ink-3">
                    {ago(d.deployedAt)}
                  </time>
                </div>
                {canDelete && (
                  <DeleteRecord
                    kind="deployment"
                    id={d.id}
                    name={`${d.applicationName} ${d.version}`}
                    done="Deployment record deleted"
                    body="This record goes from the deployment history. Nothing that's online changes."
                  />
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}

async function Integrations() {
  const { integrations } = await load<{ integrations: Integration[] }>("/platform/integrations");
  return (
    <Sheet className="overflow-hidden">
      {integrations.length === 0 ? (
        <Empty icon="teams" title="No integrations recorded.">
          Open an application and add what it connects to (payments, messaging, another system) so its state is in one place.
        </Empty>
      ) : (
        <ul className="divide-y divide-rule">
          {integrations.map((i) => (
            <li key={i.id} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 px-5 py-3">
              <div className="min-w-0">
                <p>
                  <span className="font-semibold">{i.name}</span>
                  <span className="text-ink-2">
                    {" "}
                    ·{" "}
                    <Link href={`/applications/${i.applicationId}?tab=integrations`} className="text-hema hover:underline">
                      {i.applicationName}
                    </Link>
                  </span>
                </p>
                <p className="text-meta text-ink-3">
                  {[i.target, i.healthUrl ? `Checked automatically. ${checkLine(i.lastCheck, true)}` : "Status set manually"].filter(Boolean).join(" · ")}
                </p>
              </div>
              <HealthMark status={i.status} label={HEALTH[i.status]} />
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}

