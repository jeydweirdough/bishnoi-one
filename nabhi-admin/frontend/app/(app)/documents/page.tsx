import { getMe, load } from "@/src/platform/lib/api";
import type { CorporateDocument } from "@/src/platform/lib/types";
import { DocumentsScreen } from "@/src/screens/documents";

export const metadata = { title: "Documents" };

export default async function Page() {
  const [documents, me] = await Promise.all([load<CorporateDocument[]>("/admin/documents"), getMe()]);
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  return <DocumentsScreen documents={documents} canImport={may("documents.create") && may("documents.edit")} />;
}
