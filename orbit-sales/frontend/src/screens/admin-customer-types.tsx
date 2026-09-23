import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { CustomerType } from "@/src/platform/lib/types";
import { CustomerTypesEditor } from "../components/admin/customer-types-editor";
import { NoAccess } from "../components/admin/words";
import { SettingsTabs } from "../components/settings/settings-tabs";

export const metadata = { title: "Customer types" };

export default async function CustomerTypesPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.types")) return <NoAccess what="managing customer types" />;
  const types = await load<CustomerType[]>("/customer-types");
  return (
    <>
      <PageHeader title="Settings">
        Customer types: what kind of customer each one is. The first one switched on is what a new customer starts as. A type in use can be
        switched off (the customers keep it) but not deleted.
      </PageHeader>
      <SettingsTabs me={me} current="/admin/settings/customer-types" />
      <CustomerTypesEditor types={types} />
    </>
  );
}
