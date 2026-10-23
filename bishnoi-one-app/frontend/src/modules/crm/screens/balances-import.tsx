import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe } from "@/src/platform/lib/api";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { ImportWizard } from "@/src/modules/crm/components/import/import-wizard";

export const metadata = { title: "Upload balances" };

export default async function BalancesImportPage() {
  const me = await getCompanyMe();
  if (!can(me, "goals.import")) return <NoAccess what="uploading balances" />;
  return (
    <>
      <PageHeader title="Upload balances" crumbs={[{ href: "/crm/field", label: "Field work" }]}>
        What each customer owes, from accounting&apos;s spreadsheet: one row per customer, their name and their balance.
      </PageHeader>
      <ImportWizard kind="balances" back="/crm/field/doctors" />
    </>
  );
}
