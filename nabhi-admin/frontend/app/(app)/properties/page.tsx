import { load } from "@/src/platform/lib/api";
import type { PropertyRecord } from "@/src/platform/lib/types";
import { PropertiesScreen } from "@/src/screens/properties";

export const metadata = { title: "Properties & Leases · Executive Admin" };

export default async function Page() {
  const properties = await load<PropertyRecord[]>("/admin/properties");
  return <PropertiesScreen properties={properties} />;
}
