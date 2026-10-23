import { redirect } from "next/navigation";
import { getMe } from "@/src/modules/admin/platform/lib/api";
import { ImportScreen } from "@/src/modules/admin/screens/import";

export const metadata = { title: "Import permits" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("permits.create") || !may("permits.edit")) redirect("/admin/permits");
  return <ImportScreen kind="permits" />;
}
