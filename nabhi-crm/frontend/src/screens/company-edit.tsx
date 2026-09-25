import { notFound } from "next/navigation";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import type { Assignable, CompanyDetail, CustomerType } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { CompanyForm } from "../components/crm/company-form";
import { formLayout } from "../components/extra/load";
import { priceGroupsFor } from "../components/catalogue/price-groups";

export const metadata = { title: "Edit customer" };

export default async function EditCompanyPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await getCompanyMe();
  if (!can(me, "customers.edit")) return <NoAccess what="changing customers" />;
  const { id } = await params;
  const [company, people, types, layout, priceGroups] = await Promise.all([
    load<CompanyDetail>(`/companies/${enc(id)}`),
    load<Assignable[]>("/people/assignable"),
    load<CustomerType[]>("/customer-types"),
    formLayout("company"),
    priceGroupsFor(me),
  ]);
  if (!company.can.edit) notFound();
  return (
    <>
      <PageHeader
        title={`Edit ${company.name}`}
        crumbs={[
          { href: "/companies", label: "Customers" },
          { href: `/companies/${company.id}`, label: company.name },
        ]}
      />
      <Sheet className="px-5 pt-5 pb-6">
        <CompanyForm people={people} types={types} layout={layout} company={company} priceGroups={priceGroups} />
      </Sheet>
    </>
  );
}
