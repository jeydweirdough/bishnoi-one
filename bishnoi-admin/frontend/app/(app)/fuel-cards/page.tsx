import { Restricted } from "@/src/components/restricted";
import type { Item } from "@/src/components/operations/kinds";
import { getMe, loadQuery } from "@/src/platform/lib/api";
import { OperationsScreen } from "@/src/screens/operations";

export const metadata = { title: "Fuel cards" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("vehicles.view")) return <Restricted what="the fuel cards" />;
  const items = (await loadQuery<{ records: Item[] }>(`query Records($path: String!) { records(path: $path) }`, { path: "fleet-cards" }, ["records"])).records;
  return <OperationsScreen path="fleet-cards" items={items} can={{ create: may("vehicles.create"), edit: may("vehicles.edit"), delete: may("vehicles.delete") }} />;
}
