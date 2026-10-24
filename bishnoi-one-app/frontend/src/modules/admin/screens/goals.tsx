import { managersOnly } from "@/src/modules/admin/components/gate";
import { GoalTargetsEditor } from "@/src/modules/admin/components/goal-targets";
import { PageHeader } from "@/src/modules/admin/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/modules/admin/platform/lib/api";
import type { GoalTargets } from "@/src/modules/admin/platform/lib/types";

export const metadata = { title: "Goals" };

export default async function GoalsPage() {
  const stop = await managersOnly();
  if (stop) return stop;
  const [data, me] = await Promise.all([load<GoalTargets>("/admin/goals"), getCompanyMe()]);
  return (
    <>
      <PageHeader title="Goals">
        The targets each division is measured against on everyone&apos;s home page: reps on their own month, team leads and
        division heads on their team, executives on every division.
      </PageHeader>
      <GoalTargetsEditor data={data} org={me.org} />
    </>
  );
}
