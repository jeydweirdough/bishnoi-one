import { Restricted } from "@/src/components/restricted";
import { getMe, loadQuery } from "@/src/platform/lib/api";
import type { PropertyRecord } from "@/src/platform/lib/types";
import { PropertiesScreen } from "@/src/screens/properties";

export const metadata = { title: "Properties" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("properties.view")) return <Restricted what="the properties" />;
  const properties = (await loadQuery<{ properties: PropertyRecord[] }>("query Properties { properties }", {}, ["properties"])).properties;
  return <PropertiesScreen properties={properties} canImport={may("properties.create") && may("properties.edit")} can={{ create: may("properties.create"), edit: may("properties.edit"), delete: may("properties.delete") }} />;
}
