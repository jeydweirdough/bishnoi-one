import { redirect } from "next/navigation";
import { getMe } from "@/src/modules/admin/platform/lib/api";
import { ImportScreen } from "@/src/modules/admin/screens/import";

export const metadata = { title: "Import documents" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("documents.create") || !may("documents.edit")) redirect("/admin/documents");
  return <ImportScreen kind="documents" />;
}
