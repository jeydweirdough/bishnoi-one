import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { RevenueTargets } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { TargetsForm } from "../components/deals/targets-form";
import { shiftMonth } from "../components/field/words";

export const metadata = { title: "Revenue targets" };

export default async function DealTargetsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  if (!can(me, "goals.manage")) return <NoAccess what="setting revenue targets" />;
  const asked = (await searchParams).month;
  const data = await load<RevenueTargets>(`/sales/targets${typeof asked === "string" ? `?month=${enc(asked)}` : ""}`);
  const before = shiftMonth(data.month, -1);
  const previous = await load<RevenueTargets>(`/sales/targets?month=${before}`);
  const fmt = makeFormat(me.org);
  const name = `${fmt.monthLabel(data.month)} ${data.month.slice(0, 4)}`;
  return (
    <>
      <PageHeader title={`Revenue targets for ${name}`} crumbs={[{ href: `/deals?results=${data.month}`, label: "Sales results" }]}>
        What each seller aims to win this month, counted from the deals they win. A team&apos;s target is its people&apos;s added up.
      </PageHeader>
      <Sheet className="max-w-2xl px-5 pt-3 pb-5">
        <TargetsForm org={me.org} data={data} previous={previous} monthName={name} previousName={fmt.monthLabel(before)} />
      </Sheet>
    </>
  );
}
