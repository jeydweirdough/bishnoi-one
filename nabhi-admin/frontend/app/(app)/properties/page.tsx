import { getMe, load } from "@/src/platform/lib/api";
import type { PropertyRecord } from "@/src/platform/lib/types";
import { PropertiesScreen } from "@/src/screens/properties";

export const metadata = { title: "Properties" };

export default async function Page() {
  const [properties, me] = await Promise.all([load<PropertyRecord[]>("/admin/properties"), getMe()]);
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  return <PropertiesScreen properties={properties} canImport={may("properties.create") && may("properties.edit")} />;
}
