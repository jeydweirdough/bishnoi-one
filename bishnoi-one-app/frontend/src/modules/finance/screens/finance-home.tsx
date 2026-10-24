import { Figure } from "@/src/modules/finance/platform/ui/figure";
import { PageHeader, SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { CashBalances } from "@/src/modules/finance/dashboard/cash";
import { DashboardSection } from "@/src/modules/finance/dashboard/sections";
import type { Dashboard } from "@/src/modules/finance/dashboard/types";
import type { FundCounts } from "@/src/modules/finance/funds/types";

// Finance's overview. A role made for the finance team gets the sections its
// work calls for (GET /finance/dashboard, planned 2026-10-22); the starting
// roles (Administrator, Finance Staff, Auditor) keep the overview as it was:
// what's waiting on Finance, and the balances that matter for cash advances.

export const metadata = { title: "Overview" };

export default async function FinanceHome() {
  const me = await getCompanyMe();
  const dashboard = await load<Dashboard>("/finance/dashboard");
  return (
    <>
      <PageHeader title="Overview">{me.user.fullName}, here is what needs Finance&apos;s action today.</PageHeader>
      <div className="space-y-5">
        {dashboard.kept ? (
          <KeptOverview org={me.org} />
        ) : (
          dashboard.sections.map((s) => <DashboardSection key={s.key} section={s} org={me.org} />)
        )}
      </div>
    </>
  );
}

/** The overview as it was before the dashboards: marketing requests by step, and balances. */
async function KeptOverview({ org }: { org: Org }) {
  const counts = await load<FundCounts & { to_settle: number }>("/finance/funds/counts");
  return (
    <>
      <Sheet>
        <div className="px-5 pt-4">
          <SectionTitle icon="payments">Marketing requests</SectionTitle>
        </div>
        <div className="grid grid-cols-2 divide-x divide-rule sm:grid-cols-4">
          <Figure label="For release" value={counts.to_release} href="/finance/funds" />
          <Figure label="For review" value={counts.to_check} href="/finance/funds/review" />
          <Figure label="For settlement" value={counts.to_settle} href="/finance/funds/settlement" />
          <Figure label="Overdue liquidations" value={counts.overdue} href="/finance/funds/outstanding" flag />
        </div>
      </Sheet>
      <CashBalances org={org} />
    </>
  );
}
