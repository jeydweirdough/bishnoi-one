import { managersOnly } from "@/src/modules/admin/components/gate";
import { RecordListsEditor } from "@/src/modules/admin/components/record-lists";
import { PageHeader } from "@/src/modules/admin/platform/ui/sheet";
import { load } from "@/src/modules/admin/platform/lib/api";
import type { ListSettings } from "@/src/modules/admin/platform/lib/types";

export const metadata = { title: "Lists" };

export default async function ListsPage() {
  const stop = await managersOnly();
  if (stop) return stop;
  const data = await load<ListSettings>("/admin/lists");
  return (
    <>
      <PageHeader title="Lists">
        The words your company uses for its own records: what sort of customer it keeps, how your people record having dealt with
        one, and how a call went. Rename a choice and every screen says the new word at once, without touching a single record.
        The lists the Orders app offers are in Settings &rarr; Orders.
      </PageHeader>
      <RecordListsEditor data={data} />
    </>
  );
}
