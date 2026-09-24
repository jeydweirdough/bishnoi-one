// Applications: every app on the platform, whether it's working, what was
// deployed and what each connects to.
import Link from "next/link";
import type { ReactNode } from "react";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { load } from "@/src/platform/lib/api";
import { getStaff } from "@/src/components/gate";
import { HealthMark, Tabs } from "@/src/components/marks";
import { RegisterApplication } from "@/src/components/applications/application-forms";
import { EnvironmentMark } from "@/src/components/applications/marks";
import { checkLine, uptimeText } from "@/src/components/applications/words";
import type { Application, Deployment, Integration } from "@/src/lib/types";
import { HEALTH, ago, when } from "@/src/lib/words";

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
      {tab === "deployments" && <Deployments />}
      {tab === "integrations" && <Integrations />}
    </>
  );
}

function Figure({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-ink-3">{label}</dt>
      <dd className="font-semibold text-ink tabular-nums">{children}</dd>
    </div>
  );
}

async function Registry({ retired, canAdminister }: { retired: boolean; canAdminister: boolean }) {
  const { applications } = await load<{ applications: Application[] }>(`/platform/applications${retired ? "?retired=true" : ""}`);
  return (
    <>
      <div className="mb-4">
        <ToggleLinks
          current={retired ? "all" : "active"}
          options={[
            { value: "active", label: "In use", href: "/applications" },
            { value: "all", label: "With retired ones", href: "/applications?retired=1" },
          ]}
        />
      </div>
      <Sheet className="overflow-hidden">
        {applications.length === 0 ? (
          <Empty icon="apps" title="No applications yet.">
            {canAdminister ? "Register one with its health address, and the platform starts checking it." : "A Platform Admin registers them."}
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {applications.map((a) => (
              <li key={a.id} className="px-5 py-4">
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                  <p className="min-w-0">
                    <Link href={`/applications/${a.id}`} className="font-semibold text-hema hover:underline">
                      {a.name}
                    </Link>
                    <span className="ml-2 font-mono text-meta text-ink-3">{a.key}</span>
                  </p>
                  <HealthMark status={a.status} />
                </div>
                <p className="mt-0.5 text-meta text-ink-2">
                  {a.statusNote && <span className="text-ink">{a.statusNote} · </span>}
                  {a.isActive ? checkLine(a.lastCheck, Boolean(a.healthUrl)) : "Retired: not checked."}
                </p>
                <dl className="mt-2 grid grid-cols-3 gap-x-5 gap-y-2 text-meta sm:grid-cols-6">
                  <Figure label="Version">{a.version ?? "—"}</Figure>
                  <Figure label="Up, last 24 h">{uptimeText(a.uptime)}</Figure>
                  <Figure label="Companies">{a.companyCount ?? 0}</Figure>
                  <Figure label="Users">{(a.userCount ?? 0).toLocaleString("en-PH")}</Figure>
                  <Figure label="Open tickets">
                    {a.openTickets ? (
                      <Link href={`/support?application=${a.id}`} className="text-hema hover:underline">
                        {a.openTickets}
                      </Link>
                    ) : (
                      0
                    )}
                  </Figure>
                  <Figure label="Incidents now">
                    {a.activeIncidents ? (
                      <Link href={`/applications/${a.id}?tab=issues`} className="text-danger hover:underline">
                        {a.activeIncidents}
                      </Link>
                    ) : (
                      0
                    )}
                  </Figure>
                </dl>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}

async function Deployments() {
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
                  {[i.target, i.healthUrl ? `Checked automatically. ${checkLine(i.lastCheck, true)}` : "Status set by hand"].filter(Boolean).join(" · ")}
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

