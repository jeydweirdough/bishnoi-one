import { Restricted } from "@/src/modules/admin/components/restricted";
import type { Item } from "@/src/modules/admin/components/operations/kinds";
import { getMe, loadQuery } from "@/src/modules/admin/platform/lib/api";
import { OperationsScreen } from "@/src/modules/admin/screens/operations";

export const metadata = { title: "Fuel cards" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("vehicles.view")) return <Restricted what="the fuel cards" />;
  const items = (await loadQuery<{ records: Item[] }>(`query Records($path: String!) { records(path: $path) }`, { path: "fleet-cards" }, ["records"])).records;
  return <OperationsScreen path="fleet-cards" items={items} can={{ create: may("vehicles.create"), edit: may("vehicles.edit"), delete: may("vehicles.delete") }} />;
}
