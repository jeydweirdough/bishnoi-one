import Link from "next/link";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { Figure } from "@/src/platform/ui/figure";
import { Icon, type IconName } from "@/src/platform/ui/icons";
import { Flag } from "@/src/platform/ui/marks";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { ExecutiveDashboardSummary } from "@/src/platform/lib/types";

export const metadata = { title: "Executive Admin Cockpit" };

export default async function ExecutiveDashboardPage() {
  const me = await getCompanyMe();
  const data = await load<ExecutiveDashboardSummary>("/admin/dashboard");

  const { stats, countdownHighlights } = data;

  const urgentCount =
    (stats.permits?.overdue ?? 0) +
    (stats.permits?.urgent ?? 0) +
    (stats.immigration?.overdue ?? 0) +
    (stats.tickets?.urgent ?? 0) +
    (stats.notifications?.critical ?? 0);

  return (
    <>
      <PageHeader
        title={`${me.org.name} · Executive Office`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href="/tickets"
              className="inline-flex h-8 items-center gap-1.5 rounded-[2px] bg-hema px-3 text-meta font-medium text-white hover:bg-hema-hover"
            >
              <Icon name="tickets" className="size-3.5" />
              <span>Raise Concern</span>
            </Link>
            <Link
              href="/notifications"
              className="inline-flex h-8 items-center gap-1.5 rounded-[2px] border border-rule-strong bg-sheet px-3 text-meta font-medium text-ink hover:bg-bench"
            >
              <Icon name="notifications" className="size-3.5 text-ink-3" />
              <span>Alerts Matrix ({stats.notifications?.unread ?? 0})</span>
            </Link>
          </div>
        }
      >
        Executive administration cockpit, real-time renewal countdowns, permits, expatriate compliance, leases & office concerns.
      </PageHeader>

      {/* Top Figure KPI Metrics */}
      <div className="mb-5 grid gap-5">
        <Sheet className="grid divide-y divide-rule sm:grid-cols-2 lg:grid-cols-5 sm:divide-x sm:divide-y-0">
          <Figure
            label="Permits & Accreditations"
            value={stats.permits?.total ?? 0}
            flag={Boolean((stats.permits?.overdue ?? 0) > 0 || (stats.permits?.urgent ?? 0) > 0)}
            href="/permits"
          />
          <Figure
            label="Expatriate Compliance"
            value={stats.immigration?.total ?? 0}
            flag={Boolean((stats.immigration?.overdue ?? 0) > 0 || (stats.immigration?.expiringSoon ?? 0) > 0)}
            href="/immigration"
          />
          <Figure
            label="Corporate Documents"
            value={stats.documents?.total ?? 0}
            href="/documents"
          />
          <Figure
            label="Properties & Leases"
            value={stats.properties?.total ?? 0}
            flag={Boolean((stats.properties?.leasesExpiring ?? 0) > 0)}
            href="/properties"
          />
          <Figure
            label="Open Concerns & Tickets"
            value={stats.tickets?.totalOpen ?? 0}
            flag={Boolean((stats.tickets?.urgent ?? 0) > 0)}
            href="/tickets"
          />
        </Sheet>
      </div>

      {/* Urgent Attention Alert Banner (if any) */}
      {urgentCount > 0 && (
        <Sheet className="mb-5 border-l-4 border-eosin bg-sheet px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-eosin-tint text-eosin">
                <Icon name="countdown" className="size-4" />
              </span>
              <div>
                <h3 className="text-sm font-semibold text-ink">
                  {urgentCount} compliance milestone(s) require executive intervention
                </h3>
                <p className="text-meta text-ink-3">
                  Urgent expirations under 15 days, pending agency renewals, or high-priority office concerns.
                </p>
              </div>
            </div>
            <Link
              href="/notifications"
              className="inline-flex h-8 items-center gap-1.5 rounded-[2px] bg-eosin px-3 text-meta font-semibold text-white hover:bg-eosin/90"
            >
              <span>Review Urgent Alerts</span>
            </Link>
          </div>
        </Sheet>
      )}

      {/* Real-time Expiration Countdowns Cockpit */}
      <Sheet className="mb-5 px-5 py-4">
        <SectionTitle
          icon="countdown"
          action={
            <Link href="/notifications" className="text-meta font-medium text-hema hover:underline">
              View all alerts &rarr;
            </Link>
          }
        >
          Proactive Renewal Countdowns & Expiration Matrix
        </SectionTitle>

        {countdownHighlights.length === 0 ? (
          <Empty title="All compliance items in good standing" icon="approvals">
            No registrations, expat permits, or property leases expiring within the 60-day window.
          </Empty>
        ) : (
          <div className="mt-3 divide-y divide-rule">
            {countdownHighlights.map((item) => (
              <div
                key={`${item.entityType}-${item.entityId}`}
                className="flex flex-wrap items-center justify-between gap-3 py-3 transition-colors hover:bg-bench/40 px-2 rounded-[2px]"
              >
                <div className="flex min-w-0 items-start gap-3">
                  <div className="mt-0.5 shrink-0">
                    <CountdownBadge daysRemaining={item.daysRemaining} urgencyTier={item.urgencyTier} />
                  </div>
                  <div className="min-w-0">
                    <Link
                      href={item.actionPath}
                      className="font-semibold text-ink hover:text-hema hover:underline truncate block"
                    >
                      {item.title}
                    </Link>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-meta text-ink-3">
                      <span>{item.subtitle}</span>
                      <span>&bull;</span>
                      <span>Ref: {item.reference}</span>
                      <span>&bull;</span>
                      <span>Target: {new Date(item.dueDate).toLocaleDateString("en-PH", { dateStyle: "medium" })}</span>
                    </div>
                  </div>
                </div>

                <Link
                  href={item.actionPath}
                  className="inline-flex h-7 shrink-0 items-center rounded-[2px] border border-rule px-2.5 text-stamp font-semibold text-ink-2 hover:bg-bench hover:text-ink uppercase"
                >
                  Manage
                </Link>
              </div>
            ))}
          </div>
        )}
      </Sheet>

      {/* Corporate Executive Office Operational Navigation Grid */}
      <Sheet className="px-5 py-4">
        <SectionTitle icon="exec">Executive Administration Domains</SectionTitle>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Link
            href="/permits"
            className="group block rounded-[2px] border border-rule p-4 transition-colors hover:border-hema hover:bg-bench/20"
          >
            <div className="flex items-center gap-2 font-semibold text-ink group-hover:text-hema">
              <Icon name="permits" className="size-4 text-hema" />
              <span>Registrations & Permits</span>
            </div>
            <p className="mt-1 text-meta text-ink-3">
              BOC CPRS accreditation, LGU Mayor's Business Permit, SEC Annual GIS, BIR Form 0605, and FDA Licenses to Operate.
            </p>
          </Link>

          <Link
            href="/immigration"
            className="group block rounded-[2px] border border-rule p-4 transition-colors hover:border-hema hover:bg-bench/20"
          >
            <div className="flex items-center gap-2 font-semibold text-ink group-hover:text-hema">
              <Icon name="immigration" className="size-4 text-hema" />
              <span>Expatriate & Visas</span>
            </div>
            <p className="mt-1 text-meta text-ink-3">
              Bureau of Immigration ACR I-Card, DOLE Alien Employment Permit (AEP), 9(g) visas, and executive passports.
            </p>
          </Link>

          <Link
            href="/documents"
            className="group block rounded-[2px] border border-rule p-4 transition-colors hover:border-hema hover:bg-bench/20"
          >
            <div className="flex items-center gap-2 font-semibold text-ink group-hover:text-hema">
              <Icon name="documents" className="size-4 text-hema" />
              <span>Corporate Documents</span>
            </div>
            <p className="mt-1 text-meta text-ink-3">
              Directors & Officers (D&O) liability, commercial insurance policies, commercial contracts, and board resolutions.
            </p>
          </Link>

          <Link
            href="/properties"
            className="group block rounded-[2px] border border-rule p-4 transition-colors hover:border-hema hover:bg-bench/20"
          >
            <div className="flex items-center gap-2 font-semibold text-ink group-hover:text-hema">
              <Icon name="properties" className="size-4 text-hema" />
              <span>Properties & Leases</span>
            </div>
            <p className="mt-1 text-meta text-ink-3">
              Corporate headquarters, pharma warehouses, rental escalation terms, utility accounts, and 90-day renewal notice deadlines.
            </p>
          </Link>

          <Link
            href="/tickets"
            className="group block rounded-[2px] border border-rule p-4 transition-colors hover:border-hema hover:bg-bench/20"
          >
            <div className="flex items-center gap-2 font-semibold text-ink group-hover:text-hema">
              <Icon name="tickets" className="size-4 text-hema" />
              <span>Office Concerns</span>
            </div>
            <p className="mt-1 text-meta text-ink-3">
              Executive service desk, facilities repair, VIP airport transport, office supplies procurement, and courier dispatch.
            </p>
          </Link>

          <Link
            href="/notifications"
            className="group block rounded-[2px] border border-rule p-4 transition-colors hover:border-hema hover:bg-bench/20"
          >
            <div className="flex items-center gap-2 font-semibold text-ink group-hover:text-hema">
              <Icon name="notifications" className="size-4 text-hema" />
              <span>Renewal Alerts Matrix</span>
            </div>
            <p className="mt-1 text-meta text-ink-3">
              Centralized expiration milestone engine (90d, 60d, 30d, 15d, 7d, Overdue) with acknowledgment workflows.
            </p>
          </Link>
        </div>
      </Sheet>
    </>
  );
}
