import { PageHeader } from "@/src/platform/ui/sheet";
import { can, canAny } from "@/src/modules/crm/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { RetentionWindowsEditor } from "@/src/modules/crm/components/settings/retention-windows";
import type { RetentionWindows } from "@/src/modules/crm/actions/settings";

export const metadata = { title: "Retention windows" };

/** Each department's retention windows: its own, or the company's. A manager sets their own departments'. */
export default async function RetentionWindowsPage() {
  const me = await getCompanyMe();
  if (!canAny(me, ["admin.settings", "department.manage"])) return <NoAccess what="Settings" />;
  const windows = await load<RetentionWindows>("/retention/windows");
  return (
    <>
      <PageHeader title={can(me, "admin.settings") ? "Settings" : "Department settings"}>
        When a department&apos;s customers count as at risk, and as lost, on Retention. A department uses the company&apos;s unless it has its own.
      </PageHeader>
      <RetentionWindowsEditor initial={windows} />
    </>
  );
}
