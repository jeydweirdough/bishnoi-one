import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { GoalsForm } from "@/src/modules/crm/components/field/goals-form";
import type { GoalsPayload } from "@/src/modules/crm/components/field/types";
import { shiftMonth } from "@/src/modules/crm/components/field/words";

export const metadata = { title: "Field goals" };

export default async function FieldGoalsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  if (!can(me, "goals.manage")) return <NoAccess what="setting field goals" />;
  const asked = (await searchParams).month;
  const data = await load<GoalsPayload>(`/field/goals${typeof asked === "string" ? `?month=${enc(asked)}` : ""}`);
  const before = shiftMonth(data.month, -1);
  const previous = await load<GoalsPayload>(`/field/goals?month=${before}`);
  const fmt = makeFormat(me.org);
  const name = `${fmt.monthLabel(data.month)} ${data.month.slice(0, 4)}`;
  return (
    <>
      <PageHeader title={`Goals for ${name}`} crumbs={[{ href: `/crm/field?month=${data.month}`, label: "Field work" }]}>
        What each field agent aims for this month. Leave a box empty for no goal.
      </PageHeader>
      <Sheet className="px-5 pt-3 pb-5">
        <GoalsForm org={me.org} month={data.month} monthName={name} data={data} previous={previous} previousName={fmt.monthLabel(before)} />
      </Sheet>
    </>
  );
}
