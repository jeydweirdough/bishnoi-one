import { Restricted } from "@/src/components/restricted";
import type { Item } from "@/src/components/operations/kinds";
import { getMe, loadQuery } from "@/src/platform/lib/api";
import { OperationsScreen } from "@/src/screens/operations";

export const metadata = { title: "Devices issued" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("devices.view")) return <Restricted what="the devices issued" />;
  const items = (await loadQuery<{ records: Item[] }>(`query Records($path: String!) { records(path: $path) }`, { path: "devices" }, ["records"])).records;
  return <OperationsScreen path="devices" items={items} can={{ create: may("devices.create"), edit: may("devices.edit"), delete: may("devices.delete") }} />;
}
