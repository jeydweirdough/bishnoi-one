import { getMe, load } from "@/src/platform/lib/api";
import type { ComplianceRecord } from "@/src/platform/lib/types";
import { PermitsScreen } from "@/src/screens/permits";

export const metadata = { title: "Permits" };

export default async function Page() {
  const [permits, me] = await Promise.all([load<ComplianceRecord[]>("/admin/permits"), getMe()]);
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  return <PermitsScreen permits={permits} canImport={may("permits.create") && may("permits.edit")} />;
}
