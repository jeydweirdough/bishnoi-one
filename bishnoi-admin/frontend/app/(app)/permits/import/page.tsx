import { redirect } from "next/navigation";
import { getMe } from "@/src/platform/lib/api";
import { ImportScreen } from "@/src/screens/import";

export const metadata = { title: "Import permits" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("permits.create") || !may("permits.edit")) redirect("/permits");
  return <ImportScreen kind="permits" />;
}
