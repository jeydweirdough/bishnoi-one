import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe } from "@/src/platform/lib/api";
import { NoAccess } from "../components/admin/words";
import { ImportWizard } from "../components/import/import-wizard";

export const metadata = { title: "Upload balances" };

export default async function BalancesImportPage() {
  const me = await getCompanyMe();
  if (!can(me, "goals.import")) return <NoAccess what="uploading balances" />;
  return (
    <>
      <PageHeader title="Upload balances" crumbs={[{ href: "/field", label: "Field work" }]}>
        What each customer owes, from accounting&apos;s spreadsheet: one row per customer, their name and their balance.
      </PageHeader>
      <ImportWizard kind="balances" back="/field/doctors" />
    </>
  );
}
