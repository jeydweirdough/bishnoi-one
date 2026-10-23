import { Restricted } from "@/src/modules/admin/components/restricted";
import type { Item } from "@/src/modules/admin/components/operations/kinds";
import { getMe, loadQuery } from "@/src/modules/admin/platform/lib/api";
import { OperationsScreen } from "@/src/modules/admin/screens/operations";

export const metadata = { title: "Devices issued" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("devices.view")) return <Restricted what="the devices issued" />;
  const items = (await loadQuery<{ records: Item[] }>(`query Records($path: String!) { records(path: $path) }`, { path: "devices" }, ["records"])).records;
  return <OperationsScreen path="devices" items={items} can={{ create: may("devices.create"), edit: may("devices.edit"), delete: may("devices.delete") }} />;
}
