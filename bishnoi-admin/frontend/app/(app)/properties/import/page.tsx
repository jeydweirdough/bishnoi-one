import { redirect } from "next/navigation";
import { getMe } from "@/src/platform/lib/api";
import { ImportScreen } from "@/src/screens/import";

export const metadata = { title: "Import properties" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("properties.create") || !may("properties.edit")) redirect("/properties");
  return <ImportScreen kind="properties" />;
}
