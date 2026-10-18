import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { KpiTargets } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { shiftMonth } from "../components/field/words";
import { TargetsGrid } from "../components/kpis/targets-grid";
import { IN_MENU, type Place } from "./performance";

export const metadata = { title: "Targets" };

export default async function KpiTargetsPage({ searchParams, place = IN_MENU }: { searchParams: Promise<Record<string, string | string[] | undefined>>; place?: Place }) {
  const me = await getCompanyMe();
  if (!can(me, "goals.manage")) return <NoAccess what="setting targets" />;
  const asked = (await searchParams).month;
  const data = await load<KpiTargets>(`/kpi-targets${typeof asked === "string" ? `?month=${enc(asked)}` : ""}`);
  const before = shiftMonth(data.month, -1);
  const previous = await load<KpiTargets>(`/kpi-targets?month=${before}`);
  const fmt = makeFormat(me.org);
  const name = `${fmt.monthLabel(data.month)} ${data.month.slice(0, 4)}`;
  return (
    <>
      <PageHeader title={`Targets for ${name}`} crumbs={place.tabs ? undefined : [{ href: `${place.results}?month=${data.month}`, label: "Performance" }]}>
        Each measure&apos;s target for the month, per person and per team. Leave a box empty for no target. What is measured, and for whom, is set under
        Settings → Performance.
      </PageHeader>
      {place.tabs}
      <TargetsGrid org={me.org} data={data} previous={previous} monthName={name} previousName={fmt.monthLabel(before)} resultsHref={place.results} />
    </>
  );
}
