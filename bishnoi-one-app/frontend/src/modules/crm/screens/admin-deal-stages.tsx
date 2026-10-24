import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { DealLists, DealStage } from "@/src/platform/lib/types";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { DealListsEditor, DealStagesEditor } from "@/src/modules/crm/components/deals/stages-editor";

export const metadata = { title: "Deal stages" };

export default async function DealStagesPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.settings")) return <NoAccess what="managing deal stages" />;
  const [stages, lists] = await Promise.all([load<DealStage[]>("/deal-stages"), load<DealLists>("/deal-lists")]);
  return (
    <>
      <PageHeader title="Settings">
        Deal stages: the steps a deal goes through. A deal entering a stage takes its probability and forecast category; the rep can change them on the
        deal. A stage in use can be deactivated (its deals keep it) but not deleted.
      </PageHeader>
      <div className="space-y-5">
        <DealStagesEditor stages={stages} />
        <DealListsEditor lists={lists} />
      </div>
    </>
  );
}
