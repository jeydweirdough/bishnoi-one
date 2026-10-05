import { redirect } from "next/navigation";
import { getMe } from "@/src/platform/lib/api";
import { ImportScreen } from "@/src/screens/import";

export const metadata = { title: "Import expatriate documents" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("immigration.create") || !may("immigration.edit")) redirect("/immigration");
  return <ImportScreen kind="expatriates" />;
}
