// Monitoring: whether the platform and every application are working now,
// and the Platform API's own traffic.
import Link from "next/link";
import type { ReactNode } from "react";
import { Bars } from "@/src/platform/ui/bars";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { load } from "@/src/platform/lib/api";
import { HealthMark, Tabs } from "@/src/components/marks";
import { CheckNow } from "@/src/components/monitoring/check-now";
import { TrafficChart } from "@/src/components/monitoring/traffic-chart";
import { checkLine, msText, uptimeText } from "@/src/components/applications/words";
import { HealthGauges } from "@/src/components/health-gauges";
import type { Health, HealthReport, Traffic } from "@/src/lib/types";
import { HEALTH, ago, when } from "@/src/lib/words";

export const metadata = { title: "Monitoring" };

type Search = Promise<Record<string, string | string[] | undefined>>;

const HEADLINE: Record<HealthReport["overall"], { title: string; what: string }> = {
  operational: { title: "Everything is working", what: "The Platform API, its database and every application checked answered normally." },
  degraded: { title: "Something is slow or under maintenance", what: "People can work, but not everything is as it should be. See which below." },
  down: { title: "Something is down", what: "At least one part isn't answering. See which below; an incident tells the people it reaches." },
};

const PERIODS = [
  { value: "1", label: "1 h" },
  { value: "6", label: "6 h" },
  { value: "24", label: "24 h" },
  { value: "168", label: "7 d" },
];

export default async function MonitoringPage({ searchParams }: { searchParams: Search }) {
  const params = await searchParams;
  const tab = params.tab === "traffic" ? "traffic" : "health";
  const hours = PERIODS.find((p) => p.value === params.hours)?.value ?? "6";
  return (
    <>
      <PageHeader title="Monitoring">Whether the platform and its applications are working, and how busy the Platform API is.</PageHeader>
      <Tabs
        current={tab}
        tabs={[
          { key: "health", label: "Health", href: "/monitoring" },
          { key: "traffic", label: "Traffic", href: "/monitoring?tab=traffic" },
        ]}
      />
      {tab === "health" ? <HealthView /> : <TrafficView hours={hours} />}
    </>
  );
}

/** One thing that's checked: its name, its state, and what the check said. */
function Row({ name, status, detail, figures }: { name: ReactNode; status: Health; detail?: ReactNode; figures?: [string, string][] }) {
  return (
    <li className="grid gap-x-5 gap-y-1 py-3 sm:grid-cols-[minmax(0,1fr)_auto]">
      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-semibold">{name}</span>
          <HealthMark status={status} />
        </p>
        {detail && <p className="mt-0.5 text-meta text-ink-2">{detail}</p>}
      </div>
      {figures && (
        <dl className="flex gap-x-5 text-meta sm:justify-end">
          {figures.map(([label, value]) => (
            <div key={label}>
              <dt className="text-ink-3">{label}</dt>
              <dd className="font-semibold tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      )}
    </li>
  );
}

async function HealthView() {
  const report = await load<HealthReport>("/platform/monitoring");
  const headline = HEADLINE[report.overall];
  const since = report.checkedAt ? Math.max(0, Math.round((Date.now() - Date.parse(report.checkedAt)) / 1000)) : null;
  const sinceWords = since == null ? "Not checked yet" : since < 90 ? `Checked ${since} s ago` : `Checked ${ago(report.checkedAt)}`;
  const db = report.database;

  return (
    <div className="space-y-5">
      <Sheet className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 px-5 py-4">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="text-heading">{headline.title}</span>
            <HealthMark status={report.overall} />
          </p>
          <p className="mt-0.5 text-meta text-ink-2">{headline.what}</p>
          <p className="mt-1 text-meta text-ink-3">
            <time dateTime={report.checkedAt ?? undefined} title={when(report.checkedAt)}>
              {sinceWords}
            </time>
            . Rechecked in the background when someone opens a screen and the last check is more than {report.staleSeconds} s old; Check now asks straight away.
          </p>
        </div>
        <CheckNow />
      </Sheet>

      <Sheet className="px-5 pt-5 pb-5">
        <HealthGauges health={report} />
      </Sheet>

      <Sheet className="px-5 pt-4 pb-1">
        <SectionTitle icon="monitoring">The platform</SectionTitle>
        <ul className="divide-y divide-rule">
          <Row
            name="Platform API"
            status={report.platformApi.status}
            detail={
              report.platformApi.status === "operational"
                ? "Answering; this page came through it."
                : `${report.platformApi.failedPercent}% of its requests failed in the last 15 minutes.`
            }
            figures={[
              ["Failed, 15 min", `${report.platformApi.failedPercent}%`],
              ["Average", msText(report.platformApi.averageMs)],
            ]}
          />
          <Row
            name="Database"
            status={db.status}
            detail={db.checkedAt ? `${db.detail ? `${db.detail.replace(/\.$/, "")} · ` : ""}checked ${ago(db.checkedAt)}` : "Not checked yet."}
            figures={[["Answered in", msText(db.ms)]]}
          />
        </ul>
      </Sheet>

      <Sheet className="px-5 pt-4 pb-1">
        <SectionTitle icon="apps">Applications</SectionTitle>
        {report.applications.length === 0 ? (
          <Empty icon="apps" title="No applications to check.">
            Register them in Applications with a health address, and they&apos;re checked here.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {report.applications.map((a) => (
              <Row
                key={a.id}
                name={
                  <Link href={`/applications/${a.id}`} className="text-hema hover:underline">
                    {a.name}
                  </Link>
                }
                status={a.status}
                detail={
                  <>
                    {a.statusNote && <span className="text-ink">{a.statusNote} · </span>}
                    {checkLine(a.lastCheck, a.monitored)}
                  </>
                }
                figures={[
                  ["Answered in", msText(a.lastCheck?.ms)],
                  ["Up, 24 h", uptimeText(a.uptime)],
                ]}
              />
            ))}
          </ul>
        )}
      </Sheet>

      <Sheet className="px-5 pt-4 pb-1">
        <SectionTitle icon="teams">Integrations</SectionTitle>
        {report.integrations.length === 0 ? (
          <Empty icon="teams" title="No integrations recorded.">
            Add what each application connects to on its page, under Integrations.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {report.integrations.map((i) => (
              <Row
                key={i.id}
                name={
                  <>
                    {i.name} <span className="font-normal text-ink-2">· {i.applicationName}</span>
                  </>
                }
                status={i.status}
                detail={[i.target, i.monitored ? `Checked automatically. ${checkLine(i.lastCheck, true)}` : "Status set by hand"].filter(Boolean).join(" · ")}
                figures={i.monitored ? [["Answered in", msText(i.lastCheck?.ms)]] : undefined}
              />
            ))}
          </ul>
        )}
      </Sheet>
    </div>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="flex min-w-0 flex-col-reverse justify-end bg-sheet px-5 py-4">
      <dt className="mt-0.5 text-meta text-ink-3">
        {label}
        {note && <span className="block">{note}</span>}
      </dt>
      <dd className="text-figure text-ink tabular-nums">{value}</dd>
    </div>
  );
}

async function TrafficView({ hours }: { hours: string }) {
  const traffic = await load<Traffic>(`/platform/traffic?hours=${hours}`);
  const s = traffic.summary;
  const period = PERIODS.find((p) => p.value === hours)!.label;
  const measured = traffic.applicationResponse.filter((a) => a.ms != null);
  const silent = traffic.applicationResponse.filter((a) => a.ms == null);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-meta text-ink-2">
          This is the Platform API&apos;s own traffic: the requests this console and the other apps make of it. Each application counts its own requests; what the
          platform sees of them is how fast each answers its health check, below.
        </p>
        <ToggleLinks current={hours} options={PERIODS.map((p) => ({ ...p, href: `/monitoring?tab=traffic&hours=${p.value}` }))} />
      </div>

      <Sheet className="overflow-hidden">
        <dl className="grid grid-cols-2 gap-px bg-rule sm:grid-cols-4">
          <Stat label="Requests a minute" value={s.requestsPerMinute.toLocaleString("en-PH")} note="over the last 5 minutes" />
          <Stat label={`Requests, last ${period}`} value={s.requests.toLocaleString("en-PH")} />
          <Stat label="Failed" value={`${s.failedPercent}%`} note={`${s.failed.toLocaleString("en-PH")} the API's own errors`} />
          <Stat label="Refused" value={s.refused.toLocaleString("en-PH")} note="turned away: not signed in, not allowed, bad input" />
          <Stat label="Average answer" value={msText(s.averageMs)} />
          <Stat label="Slowest answer" value={msText(s.slowestMs)} />
          <Stat label="Staff signed in" value={s.activeSessions.toLocaleString("en-PH")} note="sessions not yet ended" />
          <div aria-hidden className="bg-sheet max-sm:hidden" />
        </dl>
      </Sheet>

      <Sheet className="px-5 pt-4 pb-5">
        <SectionTitle icon="trend">Requests over the last {period}</SectionTitle>
        <div className="mt-4">
          {traffic.series.length === 0 ? (
            <Empty icon="trend" title="No requests in this time.">
              The API counts its requests as they come; try a longer stretch.
            </Empty>
          ) : (
            <TrafficChart traffic={traffic} now={Date.now()} />
          )}
        </div>
      </Sheet>

      <Sheet className="px-5 pt-4 pb-5">
        <SectionTitle icon="apps">Response time by application</SectionTitle>
        <p className="mt-1 text-meta text-ink-3">How long each took to answer its latest health check.</p>
        {traffic.applicationResponse.length === 0 ? (
          <Empty icon="apps" title="No applications to show.">
            Register them in Applications with a health address.
          </Empty>
        ) : (
          <>
            {measured.length > 0 && <Bars unit="ms" rows={measured.map((a) => ({ label: `${a.name} · ${HEALTH[a.status]}`, value: a.ms ?? 0, href: `/applications/${a.id}` }))} />}
            {silent.length > 0 && (
              <ul className="mt-3 space-y-1 text-meta text-ink-2">
                {silent.map((a) => (
                  <li key={a.id} className="flex flex-wrap items-center gap-x-3">
                    <Link href={`/applications/${a.id}`} className="text-hema hover:underline">
                      {a.name}
                    </Link>
                    <HealthMark status={a.status} />
                    <span className="text-ink-3">no answer time</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Sheet>
    </div>
  );
}
