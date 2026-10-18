import { Restricted } from "@/src/components/restricted";
import type { Material } from "@/src/actions/materials";
import { getMe, load } from "@/src/platform/lib/api";
import { MaterialsScreen } from "@/src/screens/materials";

export const metadata = { title: "Promotional materials" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("materials.view")) return <Restricted what="the promotional materials" />;
  const data = await load<{ items: Material[]; kinds: string[]; linked: { pharmacy: boolean; crm: boolean } }>("/admin/materials");
  return <MaterialsScreen data={data} canCreate={may("materials.create")} />;
}
