import { Restricted } from "@/src/modules/admin/components/restricted";
import { getMe, loadQuery } from "@/src/modules/admin/platform/lib/api";
import type { ComplianceRecord } from "@/src/modules/admin/platform/lib/types";
import { PermitsScreen } from "@/src/modules/admin/screens/permits";

export const metadata = { title: "Permits" };

export default async function Page() {
  const me = await getMe();
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  if (!may("permits.view")) return <Restricted what="the permits" />;
  const permits = (await loadQuery<{ permits: ComplianceRecord[] }>("query Permits { permits }", {}, ["permits"])).permits;
  return <PermitsScreen permits={permits} canImport={may("permits.create") && may("permits.edit")} can={{ create: may("permits.create"), edit: may("permits.edit"), delete: may("permits.delete") }} />;
}
