import Link from "next/link";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { HealthChart, RenewalsChart } from "@/src/components/overview-charts";
import { ExportButton } from "@/src/components/sheet-actions";
import { LinkButton } from "@/src/platform/ui/button";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import type { ExecutiveDashboardSummary } from "@/src/platform/lib/types";

export const metadata = { title: "Overview" };

/** What needs attention: how current each area is against its target, when
 *  renewals fall due, and the next ones to act on. Each area's own page has
 *  the rest, so nothing is repeated here. */
export default async function ExecutiveDashboardPage() {
  const { stats, countdownHighlights, health, requests, renewalsByMonth } = await load<ExecutiveDashboardSummary>("/admin/dashboard");

  const urgentCount =
    (stats.permits?.overdue ?? 0) +
    (stats.permits?.urgent ?? 0) +
    (stats.immigration?.overdue ?? 0) +
    (stats.tickets?.urgent ?? 0) +
    (stats.notifications?.critical ?? 0);
  const unread = stats.notifications?.unread ?? 0;

  return (
    <>
      <PageHeader
        title="Overview"
        actions={
          <>
            <ExportButton kind="overview" label="Export report" />
            <LinkButton href="/notifications" icon={<Icon name="notifications" className="size-4" />}>
              Renewal alerts{unread ? ` (${unread})` : ""}
            </LinkButton>
            <LinkButton href="/tickets" variant="primary" icon={<Icon name="tickets" className="size-4" />}>
              New office request
            </LinkButton>
          </>
        }
      >
        Permits, expatriates, documents, properties and office requests that need attention.
      </PageHeader>

      {urgentCount > 0 && (
        <Sheet className="mb-5 flex flex-wrap items-center justify-between gap-4 border-l-4 border-eosin px-5 py-3.5">
          <div>
            <p className="text-sm font-semibold text-ink">
              {urgentCount} {urgentCount === 1 ? "item needs" : "items need"} action
            </p>
            <p className="text-meta text-ink-3">Overdue, or due within 15 days, and urgent office requests.</p>
          </div>
          <LinkButton href="/notifications" size="sm">
            Review alerts
          </LinkButton>
        </Sheet>
      )}

      <div className="mb-5 grid gap-5 lg:grid-cols-5">
        <Sheet className="px-5 pt-4 pb-4 lg:col-span-3">
          <SectionTitle icon="approvals">Compliance health</SectionTitle>
          <HealthChart areas={health} requests={requests} />
        </Sheet>
        <Sheet className="px-5 pt-4 pb-4 lg:col-span-2">
          <SectionTitle icon="calendar">Renewals by month</SectionTitle>
          <p className="-mt-1 mb-2 text-meta text-ink-3">Permits, expatriate documents, contracts and leases falling due.</p>
          <RenewalsChart months={renewalsByMonth} />
        </Sheet>
      </div>

      <Sheet className="px-5 pt-4 pb-2">
        <SectionTitle
          icon="countdown"
          action={
            <Link href="/notifications" className="text-meta font-medium text-hema hover:underline">
              All alerts
            </Link>
          }
        >
          Due next
        </SectionTitle>
        {countdownHighlights.length === 0 ? (
          <Empty title="Nothing due in the next 60 days" icon="approvals">
            Permits, expatriate documents and leases are all current.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {countdownHighlights.map((item) => (
              <li key={`${item.entityType}-${item.entityId}`} className="flex items-center gap-3 py-3">
                <span className="w-32 shrink-0">
                  <CountdownBadge daysRemaining={item.daysRemaining} urgencyTier={item.urgencyTier} />
                </span>
                <div className="min-w-0 flex-1">
                  <Link href={item.actionPath} className="block truncate text-sm font-semibold text-ink hover:text-hema hover:underline">
                    {item.title}
                  </Link>
                  <p className="truncate text-meta text-ink-3">
                    {item.subtitle} · Due {new Date(item.dueDate).toLocaleDateString("en-PH", { dateStyle: "medium" })}
                  </p>
                </div>
                <LinkButton href={item.actionPath} size="sm" variant="quiet">
                  Open
                </LinkButton>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}
