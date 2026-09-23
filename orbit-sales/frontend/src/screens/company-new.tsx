import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { Assignable } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { CompanyForm } from "../components/crm/company-form";

export const metadata = { title: "Add a company" };

export default async function NewCompanyPage() {
  const me = await getCompanyMe();
  if (!can(me, "customers.create")) return <NoAccess what="adding customers" />;
  const people = await load<Assignable[]>("/people/assignable");
  return (
    <>
      <PageHeader title="Add a company" crumbs={[{ href: "/companies", label: "Companies" }]} />
      <Sheet className="px-5 pt-5 pb-6">
        <CompanyForm people={people} />
      </Sheet>
    </>
  );
}
