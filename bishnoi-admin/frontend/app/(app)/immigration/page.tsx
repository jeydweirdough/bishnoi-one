import { Restricted } from "@/src/components/restricted";
import { getMe, load } from "@/src/platform/lib/api";
import type { ImmigrationRecord } from "@/src/platform/lib/types";
import { ImmigrationScreen } from "@/src/screens/immigration";

export const metadata = { title: "Expatriates" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("immigration.view")) return <Restricted what="the expatriates' records" />;
  const records = await load<ImmigrationRecord[]>("/admin/immigration");
  return <ImmigrationScreen records={records} canImport={may("immigration.create") && may("immigration.edit")} can={{ create: may("immigration.create"), edit: may("immigration.edit"), delete: may("immigration.delete") }} />;
}
