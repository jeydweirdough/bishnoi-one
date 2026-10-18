import { redirect } from "next/navigation";
import Link from "next/link";
import { Clock, HomeCalendar } from "@/src/components/home-attention";
import { HealthChart, RenewalsChart } from "@/src/components/overview-charts";
import { Restricted } from "@/src/components/restricted";
import { ExportButton } from "@/src/components/sheet-actions";
import { LinkButton } from "@/src/platform/ui/button";
import { Icon } from "@/src/platform/ui/icons";
import { PageHeader, SectionTitle } from "@/src/platform/ui/sheet";
import { getMe, loadQuery } from "@/src/platform/lib/api";
import type { AreaHealth, ExecutiveDashboardSummary } from "@/src/platform/lib/types";

export const metadata = { title: "Home" };

/** Home, kept to few choices (Hick's law): one main action, then two panels as
 *  tall as the screen: the schedule (what falls due, a day at a time) on the
 *  left, and where things stand (four figures, two by two, in one container:
 *  common region) on the right. The charts wait under Trends until opened. */
export default async function ExecutiveDashboardPage() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  // The marketing assistant's work is promotional materials only: that's their home.
  if (!may("dashboard.view") && may("materials.view")) redirect("/materials");
  if (!may("dashboard.view")) return <Restricted what="home" />;
  const { stats, countdownHighlights, health, requests, renewalsByMonth } = (await loadQuery<{ dashboard: ExecutiveDashboardSummary }>("query Dashboard { dashboard }", {}, ["dashboard"])).dashboard;
  const area = (key: string) => health.find((h) => h.key === key);

  return (
    <>
      <PageHeader
        title="Home"
        actions={
          <LinkButton href="/tickets" variant="primary" icon={<Icon name="tickets" className="size-4" />}>
            New office request
          </LinkButton>
        }
      >
        <Clock /> · what&apos;s due, a day at a time
      </PageHeader>

      <div className="grid gap-5 lg:min-h-[calc(100dvh-15rem)] lg:grid-cols-[minmax(0,1.3fr)_minmax(26rem,1fr)]">
        <HomeCalendar items={countdownHighlights} canLog={may("vehicles.edit")} />

        <section aria-label="Where things stand" className="grid grid-cols-2 grid-rows-2 gap-3 rounded-[22px] border border-rule bg-sheet p-3.5">
          <RingCard title="Permits current" sub={`${area("permits")?.total ?? 0} permits · target all`} area={area("permits")} href="/permits" />
          <BarCard
            title="Vehicles"
            sub={`${stats.vehicles?.total ?? 0} · registration, insurance, PMS`}
            big={stats.vehicles?.overdue ? `${stats.vehicles.overdue} overdue` : `${stats.vehicles?.dueSoon ?? 0} due`}
            share={area("vehicles") ? (area("vehicles")!.current / Math.max(1, area("vehicles")!.total)) * 100 : 0}
            behind={Boolean(stats.vehicles?.overdue)}
            note={stats.vehicles?.dueSoon ? `${stats.vehicles.dueSoon} due within 30 days` : "Nothing due within 30 days"}
            href="/vehicles"
          />
          <BarCard
            title="Trips"
            sub="Next 30 days"
            big={String(stats.travel?.upcoming ?? 0)}
            share={stats.travel?.upcoming ? ((stats.travel.upcoming - Math.min(stats.travel.upcoming, stats.travel.waiting)) / stats.travel.upcoming) * 100 : 100}
            behind={Boolean(stats.travel?.waiting)}
            note={stats.travel?.waiting ? `${stats.travel.waiting} waiting on you` : "None waiting on you"}
            noteWarn={Boolean(stats.travel?.waiting)}
            href="/travel"
          />
          <BarCard
            title="Fuel cards"
            sub={`Active of ${(stats.fleetCards?.active ?? 0) + (stats.fleetCards?.blocked ?? 0)}`}
            big={String(stats.fleetCards?.active ?? 0)}
            note={[stats.fleetCards?.blocked ? `${stats.fleetCards.blocked} blocked` : null, stats.fleetCards?.processing ? `${stats.fleetCards.processing} processing` : null].filter(Boolean).join(" · ") || "None blocked"}
            href="/fuel-cards"
          />
        </section>
      </div>

      {/* The charts are for planning, not for today's work: there when asked for. */}
      <details className="group mt-5 rounded-[22px] border border-rule bg-sheet">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-[15px] font-semibold text-ink [&::-webkit-details-marker]:hidden">
          <span>Trends: how each area stands, and renewals by month</span>
          <span className="text-[12.5px] font-medium text-ink-3 group-open:hidden">Show</span>
          <span className="hidden text-[12.5px] font-medium text-ink-3 group-open:inline">Hide</span>
        </summary>
        <div className="grid gap-5 border-t border-rule px-5 pt-4 pb-5 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <SectionTitle icon="approvals" action={<ExportButton kind="overview" label="Export report" />}>
              How each area stands
            </SectionTitle>
            <HealthChart areas={health} requests={requests} />
          </div>
          <div className="lg:col-span-2">
            <SectionTitle icon="calendar">Renewals by month</SectionTitle>
            <p className="-mt-1 mb-2 text-meta text-ink-3">Permits, expatriate documents, contracts, leases and vehicle renewals falling due.</p>
            <RenewalsChart months={renewalsByMonth} />
          </div>
        </div>
      </details>
    </>
  );
}

/** The CRM's figure card with a ring: what share is current, against a target of all. */
function RingCard({ title, sub, area, href }: { title: string; sub: string; area?: AreaHealth; href: string }) {
  const total = Math.max(1, area?.total ?? 0);
  const share = Math.round(((area?.current ?? 0) / total) * 100);
  const r = 17;
  const full = 2 * Math.PI * r;
  const tone = area?.overdue ? "bad" : share >= 75 ? "good" : "warn";
  return (
    <Link href={href} className="flex flex-col justify-center rounded-[18px] border-[1.5px] border-ink bg-sheet px-5 py-3.5 transition-colors hover:bg-mint">
      <div className="flex items-start justify-between gap-3.5">
        <div>
          <h3 className="text-[15px] font-semibold text-ink">{title}</h3>
          <p className="mt-0.5 text-[12.5px] text-ink-3">{sub}</p>
        </div>
        <svg className="size-[54px] shrink-0" viewBox="0 0 44 44" role="img" aria-label={`${share}%`}>
          <circle cx="22" cy="22" r={r} fill="none" stroke="#e3eedf" strokeWidth="5" />
          <circle cx="22" cy="22" r={r} fill="none" stroke={tone === "good" ? "#a8d69b" : "#e8c27a"} strokeWidth="5" strokeLinecap="round" strokeDasharray={`${(share / 100) * full} ${full}`} transform="rotate(-90 22 22)" />
          <text x="22" y="25.5" textAnchor="middle" fontSize="10" fontWeight="600" fill="#141414" fontFamily="Poppins">
            {share}%
          </text>
        </svg>
      </div>
      <p className="mt-1.5 text-[26px] leading-[1.1] font-semibold tracking-[-0.02em] text-ink">
        {area?.current ?? 0} of {area?.total ?? 0}
      </p>
      <span
        className={`mt-2.5 inline-flex h-[26px] items-center gap-1.5 rounded-full px-3 text-[12.5px] font-medium ${tone === "bad" ? "bg-danger-tint text-danger" : tone === "good" ? "bg-[#e6f2e1] text-[#3f6f35]" : "bg-[#fbf0d9] text-[#8a5a00]"}`}
      >
        <span className="size-[7px] rounded-full bg-current" aria-hidden />
        {area?.overdue ? `${area.overdue} overdue` : area?.dueSoon ? `${area.dueSoon} due soon` : "All current"}
      </span>
    </Link>
  );
}

/** The CRM's figure card: the number, a bar of how much is on track, and a line of what to know. */
function BarCard({ title, sub, big, share, behind, note, noteWarn, href }: { title: string; sub: string; big: string; share?: number; behind?: boolean; note: string; noteWarn?: boolean; href: string }) {
  return (
    <Link href={href} className="flex flex-col justify-center rounded-[18px] border border-rule bg-sheet px-5 py-3.5 transition-colors hover:border-ink">
      <h3 className="text-[15px] font-semibold text-ink">{title}</h3>
      <p className="mt-0.5 text-[12.5px] text-ink-3">{sub}</p>
      <p className="mt-1.5 text-[26px] leading-[1.1] font-semibold tracking-[-0.02em] text-ink">{big}</p>
      {share !== undefined && (
        <div className="mt-3.5 h-2 overflow-hidden rounded-full bg-mint-2" aria-hidden>
          <i className={`block h-full rounded-full ${behind ? "bg-[#e8c27a]" : "bg-sage"}`} style={{ width: `${Math.max(4, Math.min(100, share))}%` }} />
        </div>
      )}
      <p className={`mt-2.5 text-[12.5px] ${noteWarn ? "font-medium text-[#8a5a00]" : "text-ink-3"}`}>{note}</p>
    </Link>
  );
}
