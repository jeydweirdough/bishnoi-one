import { load } from "@/src/platform/lib/api";
import type { CorporateDocument } from "@/src/platform/lib/types";
import { DocumentsScreen } from "@/src/screens/documents";

export const metadata = { title: "Corporate Documents · Executive Admin" };

export default async function Page() {
  const documents = await load<CorporateDocument[]>("/admin/documents");
  return <DocumentsScreen documents={documents} />;
}
