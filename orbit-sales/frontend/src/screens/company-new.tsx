import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { Assignable, CustomerType } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { CompanyForm } from "../components/crm/company-form";

export const metadata = { title: "Add a customer" };

export default async function NewCompanyPage() {
  const me = await getCompanyMe();
  if (!can(me, "customers.create")) return <NoAccess what="adding customers" />;
  const [people, types] = await Promise.all([load<Assignable[]>("/people/assignable"), load<CustomerType[]>("/customer-types")]);
  return (
    <>
      <PageHeader title="Add a customer" crumbs={[{ href: "/companies", label: "Companies" }]} />
      <Sheet className="px-5 pt-5 pb-6">
        <CompanyForm people={people} types={types} />
      </Sheet>
    </>
  );
}
