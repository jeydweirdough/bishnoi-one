import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe } from "@/src/platform/lib/api";
import { NoAccess } from "../components/admin/words";
import { ImportWizard } from "../components/import/import-wizard";

export const metadata = { title: "Import people" };

export default async function PeopleImportPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.users")) return <NoAccess what="importing people" />;
  return (
    <>
      <PageHeader title="Import people" crumbs={[{ href: "/admin/users", label: "People & access" }]}>
        Accounts from a spreadsheet, with each person&apos;s role and team: new ones added, people already here (same email) updated.
      </PageHeader>
      <ImportWizard kind="people" back="/admin/users" />
    </>
  );
}
