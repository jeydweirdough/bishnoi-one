import { Restricted } from "@/src/components/restricted";
import type { Item } from "@/src/components/operations/kinds";
import { getMe, loadQuery } from "@/src/platform/lib/api";
import { OperationsScreen } from "@/src/screens/operations";

export const metadata = { title: "Hotel and flights" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("travel.view")) return <Restricted what="the hotel and flight sponsorships" />;
  const items = (await loadQuery<{ records: Item[] }>(`query Records($path: String!) { records(path: $path) }`, { path: "travel" }, ["records"])).records;
  return <OperationsScreen path="travel" items={items} can={{ create: may("travel.create"), edit: may("travel.edit"), delete: may("travel.delete") }} />;
}
