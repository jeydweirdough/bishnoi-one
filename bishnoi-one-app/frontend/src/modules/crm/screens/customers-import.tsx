import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe } from "@/src/platform/lib/api";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { ImportWizard } from "@/src/modules/crm/components/import/import-wizard";

export const metadata = { title: "Import customers" };

export default async function CustomersImportPage() {
  const me = await getCompanyMe();
  if (!can(me, "customers.create") && !can(me, "customers.edit")) return <NoAccess what="importing customers" />;
  return (
    <>
      <PageHeader title="Import customers" crumbs={[{ href: "/crm/companies", label: "Customers" }]}>
        Customers and everything on their form, from a spreadsheet: new ones added, ones with their customer code updated.
      </PageHeader>
      <ImportWizard kind="customers" back="/crm/companies" />
    </>
  );
}
