import { getMe, load } from "@/src/platform/lib/api";
import type { ImmigrationRecord } from "@/src/platform/lib/types";
import { ImmigrationScreen } from "@/src/screens/immigration";

export const metadata = { title: "Expatriates" };

export default async function Page() {
  const [records, me] = await Promise.all([load<ImmigrationRecord[]>("/admin/immigration"), getMe()]);
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  return <ImmigrationScreen records={records} canImport={may("immigration.create") && may("immigration.edit")} />;
}
