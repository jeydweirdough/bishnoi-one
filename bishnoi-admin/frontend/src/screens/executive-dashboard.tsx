import Link from "next/link";
import { HomeAttention } from "@/src/components/home-attention";
import { HealthChart, RenewalsChart } from "@/src/components/overview-charts";
import { Restricted } from "@/src/components/restricted";
import { ExportButton } from "@/src/components/sheet-actions";
import { LinkButton } from "@/src/platform/ui/button";
import { Icon, type IconName } from "@/src/platform/ui/icons";
import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { getMe, loadQuery } from "@/src/platform/lib/api";
import type { AreaHealth, CountdownHighlight, ExecutiveDashboardSummary } from "@/src/platform/lib/types";

export const metadata = { title: "Home" };

/** Home, as the CRM's Home: figures that say where each thing stands, what
 *  needs you (late or within a week, each with its next step), what's due
 *  next, and how each area stands against its target. */
export default async function ExecutiveDashboardPage() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("dashboard.view")) return <Restricted what="home" />;
  const { stats, countdownHighlights, health, requests, renewalsByMonth } = (await loadQuery<{ dashboard: ExecutiveDashboardSummary }>("query Dashboard { dashboard }", {}, ["dashboard"])).dashboard;
  const today = new Date().toLocaleDateString("en-PH", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const attention = countdownHighlights.filter((h) => h.daysRemaining <= 7);
  const next = countdownHighlights.filter((h) => h.daysRemaining > 7).slice(0, 6);
  const area = (key: string) => health.find((h) => h.key === key);

  return (
    <>
      <PageHeader
        title="Home"
        actions={
          <>
            <ExportButton kind="overview" label="Export report" />
            <LinkButton href="/tickets" variant="primary" icon={<Icon name="tickets" className="size-4" />}>
              New office request
            </LinkButton>
          </>
        }
      >
        {today} · what&apos;s due across permits, visas, cars and trips
      </PageHeader>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
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
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:items-start">
        <HomeAttention items={attention} canLog={may("vehicles.edit")} />
        <DueNext items={next} />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-5">
        <Sheet className="px-5 pt-4 pb-4 lg:col-span-3">
          <SectionTitle icon="approvals">How each area stands</SectionTitle>
          <HealthChart areas={health} requests={requests} />
        </Sheet>
        <Sheet className="px-5 pt-4 pb-4 lg:col-span-2">
          <SectionTitle icon="calendar">Renewals by month</SectionTitle>
          <p className="-mt-1 mb-2 text-meta text-ink-3">Permits, expatriate documents, contracts, leases and vehicle renewals falling due.</p>
          <RenewalsChart months={renewalsByMonth} />
        </Sheet>
      </div>
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
    <Link href={href} className="block rounded-[22px] border-[1.5px] border-ink bg-sheet px-5 py-[18px] transition-colors hover:bg-mint">
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
      <p className="mt-2.5 text-[30px] leading-[1.1] font-semibold tracking-[-0.02em] text-ink">
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
    <Link href={href} className="block rounded-[22px] border border-rule bg-sheet px-5 py-[18px] transition-colors hover:border-ink">
      <h3 className="text-[15px] font-semibold text-ink">{title}</h3>
      <p className="mt-0.5 text-[12.5px] text-ink-3">{sub}</p>
      <p className="mt-2.5 text-[30px] leading-[1.1] font-semibold tracking-[-0.02em] text-ink">{big}</p>
      {share !== undefined && (
        <div className="mt-3.5 h-2 overflow-hidden rounded-full bg-mint-2" aria-hidden>
          <i className={`block h-full rounded-full ${behind ? "bg-[#e8c27a]" : "bg-sage"}`} style={{ width: `${Math.max(4, Math.min(100, share))}%` }} />
        </div>
      )}
      <p className={`mt-2.5 text-[12.5px] ${noteWarn ? "font-medium text-[#8a5a00]" : "text-ink-3"}`}>{note}</p>
    </Link>
  );
}

const ICON: Record<string, IconName> = {
  permit: "permits",
  immigration: "immigration",
  document: "documents",
  property: "properties",
  ticket: "tickets",
  vehicle_registration: "vehicles",
  vehicle_insurance: "vehicles",
  vehicle_pms: "vehicles",
  travel: "travel",
};

/** The CRM's timeline: what's due after this week, soonest first. */
function DueNext({ items }: { items: CountdownHighlight[] }) {
  return (
    <section className="rounded-[22px] border border-rule bg-sheet px-5 py-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[17px] font-semibold text-ink">Due next</h2>
        <Link href="/notifications" className="text-[12.5px] font-medium text-ink hover:underline">
          All alerts
        </Link>
      </div>
      {items.length === 0 ? (
        <p className="mt-3 text-sm text-ink-3">Nothing else falls due in the next 60 days.</p>
      ) : (
        <ol className="mt-3.5">
          {items.map((i, n) => (
            <li key={`${i.entityType}-${i.entityId}`} className="relative grid grid-cols-[38px_minmax(0,1fr)_auto] gap-3.5 pb-[18px] last:pb-0">
              {n < items.length - 1 && <span className="absolute top-10 bottom-0.5 left-[18px] w-[1.5px] bg-rule" aria-hidden />}
              <span className="grid size-[38px] place-items-center rounded-full border-[1.5px] border-ink bg-sheet">
                <Icon name={ICON[i.entityType] ?? "notifications"} className="size-[18px]" />
              </span>
              <div className="min-w-0">
                <Link href={i.actionPath} className="font-semibold text-ink hover:underline">
                  {i.title}
                  {i.entityType.startsWith("vehicle_") ? ` · ${i.subtitle.charAt(0).toLowerCase() + i.subtitle.slice(1)}` : ""}
                </Link>
                <p className="text-[12.5px] text-ink-3">{i.entityType.startsWith("vehicle_") ? i.reference : i.subtitle}</p>
              </div>
              <time dateTime={i.dueDate} className="text-[12.5px] whitespace-nowrap text-ink-3">
                {new Date(i.dueDate.length === 10 ? `${i.dueDate}T00:00:00` : i.dueDate).toLocaleDateString("en-PH", { weekday: "short", day: "numeric", month: "short" })}
              </time>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
