import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe } from "@/src/platform/lib/api";
import { AuditLog } from "@/src/platform/screens/audit";
import { AUDIT_FILTERS, describeAudit, describeFields } from "@/src/modules/crm/components/admin/audit-words";
import { NoAccess } from "@/src/modules/crm/components/admin/words";

export const metadata = { title: "Activity log" };

type Search = Promise<Record<string, string | string[] | undefined>>;

/** The activity log: the shared one (src/platform/screens/audit.tsx), with the CRM's words. */
export default async function AuditLogPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "admin.audit")) return <NoAccess what="the activity log" />;
  return (
    <AuditLog
      searchParams={searchParams}
      settings={{ describe: describeAudit, filters: AUDIT_FILTERS, fieldWords: describeFields, peoplePages: true }}
    />
  );
}
