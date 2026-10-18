import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { CustomerType } from "@/src/platform/lib/types";
import { CustomerTypesEditor } from "../components/admin/customer-types-editor";
import type { TeamName } from "../components/admin/teams-for";
import { NoAccess } from "../components/admin/words";

export const metadata = { title: "Customer types" };

export default async function CustomerTypesPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.types")) return <NoAccess what="managing customer types" />;
  const [types, teams] = await Promise.all([load<CustomerType[]>("/customer-types"), load<TeamName[]>("/team-names")]);
  return (
    <>
      <PageHeader title="Settings">
        Customer types: what kind of customer each one is. The first active one is what a new customer starts as. A type in use can be
        deactivated (the customers keep it) but not deleted.
      </PageHeader>
      <CustomerTypesEditor types={types} teams={teams} />
    </>
  );
}
