// Services (the Operations area, step 5): each app's service, what was deployed and the
// links between apps. Health tracking was retired from the screens.
import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { Empty, PageHeader, Sheet } from "@/src/modules/console/platform/ui/sheet";
import { ToggleLinks } from "@/src/modules/console/platform/ui/toggle-links";
import { load } from "@/src/modules/console/platform/lib/api";
import { DeleteRecord } from "@/src/modules/console/components/delete-record";
import { getStaff } from "@/src/modules/console/components/gate";
import { HealthMark, Tabs } from "@/src/modules/console/components/marks";
import { RegisterApplication } from "@/src/modules/console/components/applications/application-forms";
import { EnvironmentMark } from "@/src/modules/console/components/applications/marks";
import { checkLine } from "@/src/modules/console/components/applications/words";
import type { Application, Deployment, Integration } from "@/src/modules/console/lib/types";
import { HEALTH, ago, plural, when } from "@/src/modules/console/lib/words";

export const metadata = { title: "Services" };

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
      <PageHeader title="Services" actions={staff.canAdminister && <RegisterApplication />}>
        Each app&apos;s service: where its screens and API are, which companies use it, and what was deployed. Health tracking, incidents and support tickets were retired (step 5).
      </PageHeader>
      <Tabs current={tab} tabs={TABS.map((t) => ({ ...t, href: t.key === "registry" ? "/operations/apis" : `/operations/apis?tab=${t.key}` }))} />
      {tab === "registry" && <Registry retired={retired} canAdminister={staff.canAdminister} />}
      {tab === "deployments" && <Deployments canDelete={staff.canAdminister} />}
      {tab === "integrations" && <Integrations />}
    </>
  );
}

// Each row: the service, its address, and who uses it; the whole row opens it (Fitts's law).
function AppRow({ a }: { a: Application }) {
  return (
    <li>
      <Link
        href={`/operations/apis/${a.id}`}
        className="group grid gap-x-6 gap-y-2 border-l-4 border-transparent px-5 py-4 transition-colors hover:bg-mint focus-visible:bg-mint focus-visible:outline-none sm:grid-cols-[minmax(0,1fr)_auto]"
      >
        <span className="min-w-0">
          <span className="text-base font-semibold text-ink group-hover:underline">{a.name}</span>
          <span className="mt-0.5 block truncate text-meta text-ink-2">{a.isActive ? (a.appUrl ?? "No address yet") : "Retired"}</span>
          <span className="mt-1 block text-meta text-ink-3">
            <span className="font-mono">{a.key}</span>
            {a.no ? ` · No. ${a.no}` : ""} · {plural(a.companyCount ?? 0, "company", "companies")} · {plural(a.userCount ?? 0, "user")}
            {a.version ? ` · version ${a.version}` : ""}
          </span>
        </span>
        <span className="flex items-center sm:justify-end">
          <ChevronRight className="hidden size-4 text-ink-3 group-hover:text-ink sm:block" aria-hidden />
        </span>
      </Link>
    </li>
  );
}

async function Registry({ retired, canAdminister }: { retired: boolean; canAdminister: boolean }) {
  const { applications } = await load<{ applications: Application[] }>(`/platform/applications${retired ? "?retired=true" : ""}`);
  const sorted = [...applications].sort((x, y) => Number(y.isActive) - Number(x.isActive) || x.name.localeCompare(y.name));
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-end gap-3">
        <ToggleLinks
          current={retired ? "all" : "active"}
          options={[
            { value: "active", label: "Active", href: "/operations/apis" },
            { value: "all", label: "Include retired", href: "/operations/apis?retired=1" },
          ]}
        />
      </div>
      {applications.length === 0 ? (
        <Sheet>
          <Empty icon="apps" title="No services yet.">
            {canAdminister ? "Register each app's service with its address." : "An operator registers them."}
          </Empty>
        </Sheet>
      ) : (
        <Sheet className="overflow-hidden">
          <ul className="divide-y divide-rule">{sorted.map((a) => <AppRow key={a.id} a={a} />)}</ul>
        </Sheet>
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
                  <Link href={`/operations/apis/${d.applicationId}?tab=deployments`} className="font-semibold text-hema hover:underline">
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
                    <Link href={`/operations/apis/${i.applicationId}?tab=integrations`} className="text-hema hover:underline">
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

