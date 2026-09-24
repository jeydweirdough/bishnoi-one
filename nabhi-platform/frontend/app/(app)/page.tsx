// The dashboard: what is happening across the whole platform right now. The
// counts first, then what needs someone (incidents, tickets), then how the
// systems are doing, then what was said and done lately.
import Link from "next/link";
import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { getMe, load } from "@/src/platform/lib/api";
import { greeting } from "@/src/platform/lib/format";
import { ActivityList } from "@/src/components/activity-list";
import { getStaff } from "@/src/components/gate";
import { ActiveIncidents, Counts, Notices, SupportSummary, SystemHealth, Traffic } from "@/src/components/dashboard/parts";
import type { Dashboard } from "@/src/lib/types";

export const metadata = { title: "Dashboard" };

export default async function Page() {
  const [data, me, staff] = await Promise.all([load<Dashboard>("/platform/dashboard"), getMe(), getStaff()]);
  const firstName = me.user.fullName.split(" ")[0] || me.user.fullName;

  return (
    <>
      <PageHeader title="Dashboard">
        {greeting()}, {firstName}. You&apos;re signed in as {staff.platformRoleName}. Here&apos;s the whole platform, right now.
      </PageHeader>

      <Counts counts={data.counts} />

      <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
        <div className="grid gap-5">
          <ActiveIncidents incidents={data.incidents} />
          <SupportSummary support={data.support} overdue={data.overdue} />
        </div>
        <div className="grid gap-5">
          <SystemHealth health={data.health} />
          <Traffic traffic={data.traffic} />
          <Notices notices={data.notices} />
        </div>
      </div>

      <Sheet className="mt-5 px-5 pt-4 pb-3">
        <SectionTitle
          icon="auditLog"
          action={
            <Link href="/activity" className="text-meta font-semibold text-hema hover:underline">
              All activity
            </Link>
          }
        >
          Recent activity
        </SectionTitle>
        <ActivityList entries={data.recent} showCategory empty="Nothing done on the platform yet." />
      </Sheet>
    </>
  );
}
