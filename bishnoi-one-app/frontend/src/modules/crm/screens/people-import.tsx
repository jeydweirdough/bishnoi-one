import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe } from "@/src/platform/lib/api";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { ImportWizard } from "@/src/modules/crm/components/import/import-wizard";

export const metadata = { title: "Import people" };

export default async function PeopleImportPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.users")) return <NoAccess what="importing people" />;
  return (
    <>
      <PageHeader title="Import people" crumbs={[{ href: "/crm/admin/users", label: "People and access" }]}>
        Accounts from a spreadsheet, with each person&apos;s role and team: new ones added, people already here (same email) updated.
      </PageHeader>
      <ImportWizard kind="people" back="/crm/admin/users" />
    </>
  );
}
