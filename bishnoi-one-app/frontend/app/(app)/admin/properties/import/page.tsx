import { redirect } from "next/navigation";
import { getMe } from "@/src/modules/admin/platform/lib/api";
import { ImportScreen } from "@/src/modules/admin/screens/import";

export const metadata = { title: "Import properties" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("properties.create") || !may("properties.edit")) redirect("/admin/properties");
  return <ImportScreen kind="properties" />;
}
