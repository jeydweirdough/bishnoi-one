import { Restricted } from "@/src/components/restricted";
import { getMe, load } from "@/src/platform/lib/api";
import type { ComplianceRecord } from "@/src/platform/lib/types";
import { PermitsScreen } from "@/src/screens/permits";

export const metadata = { title: "Permits" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("permits.view")) return <Restricted what="the permits" />;
  const permits = await load<ComplianceRecord[]>("/admin/permits");
  return <PermitsScreen permits={permits} canImport={may("permits.create") && may("permits.edit")} can={{ create: may("permits.create"), edit: may("permits.edit"), delete: may("permits.delete") }} />;
}
