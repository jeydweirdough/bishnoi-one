import { Restricted } from "@/src/components/restricted";
import { getMe, load } from "@/src/platform/lib/api";
import type { CorporateDocument } from "@/src/platform/lib/types";
import { DocumentsScreen } from "@/src/screens/documents";

export const metadata = { title: "Documents" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("documents.view")) return <Restricted what="the corporate documents" />;
  const documents = await load<CorporateDocument[]>("/admin/documents");
  return <DocumentsScreen documents={documents} canImport={may("documents.create") && may("documents.edit")} can={{ create: may("documents.create"), edit: may("documents.edit"), delete: may("documents.delete") }} />;
}
