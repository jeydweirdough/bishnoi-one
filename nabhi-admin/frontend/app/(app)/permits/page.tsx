import { load } from "@/src/platform/lib/api";
import type { ComplianceRecord } from "@/src/platform/lib/types";
import { PermitsScreen } from "@/src/screens/permits";

export const metadata = { title: "Registrations & Permits · Executive Admin" };

export default async function Page() {
  const permits = await load<ComplianceRecord[]>("/admin/permits");
  return <PermitsScreen permits={permits} />;
}
