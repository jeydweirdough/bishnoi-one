import { notFound } from "next/navigation";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import type { Assignable, CompanyDetail, CustomerType } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { CompanyForm } from "../components/crm/company-form";

export const metadata = { title: "Edit company" };

export default async function EditCompanyPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await getCompanyMe();
  if (!can(me, "customers.edit")) return <NoAccess what="changing customers" />;
  const { id } = await params;
  const [company, people, types] = await Promise.all([
    load<CompanyDetail>(`/companies/${enc(id)}`),
    load<Assignable[]>("/people/assignable"),
    load<CustomerType[]>("/customer-types"),
  ]);
  if (!company.can.edit) notFound();
  return (
    <>
      <PageHeader
        title={`Edit ${company.name}`}
        crumbs={[
          { href: "/companies", label: "Companies" },
          { href: `/companies/${company.id}`, label: company.name },
        ]}
      />
      <Sheet className="px-5 pt-5 pb-6">
        <CompanyForm people={people} types={types} company={company} />
      </Sheet>
    </>
  );
}
