import { Restricted } from "@/src/modules/admin/components/restricted";
import { getMe, loadQuery } from "@/src/modules/admin/platform/lib/api";
import type { ImmigrationRecord } from "@/src/modules/admin/platform/lib/types";
import { ImmigrationScreen } from "@/src/modules/admin/screens/immigration";

export const metadata = { title: "Expatriates" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("immigration.view")) return <Restricted what="the expatriates' records" />;
  const records = (await loadQuery<{ immigration: ImmigrationRecord[] }>("query Immigration { immigration }", {}, ["immigration"])).immigration;
  return <ImmigrationScreen records={records} canImport={may("immigration.create") && may("immigration.edit")} can={{ create: may("immigration.create"), edit: may("immigration.edit"), delete: may("immigration.delete") }} />;
}
