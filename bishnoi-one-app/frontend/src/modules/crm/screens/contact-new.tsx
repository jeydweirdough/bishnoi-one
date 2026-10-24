import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { Assignable, CompanyRow, Paged } from "@/src/platform/lib/types";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { ContactForm } from "@/src/modules/crm/components/crm/contact-form";
import { formLayout } from "@/src/modules/crm/components/extra/load";

export const metadata = { title: "Add a contact" };

type Search = Promise<Record<string, string | string[] | undefined>>;

export default async function NewContactPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "customers.create")) return <NoAccess what="adding customers" />;
  const { company } = await searchParams;
  const [people, companies, fields] = await Promise.all([
    load<Assignable[]>("/people/assignable"),
    load<Paged<CompanyRow>>("/companies?limit=200"),
    formLayout("contact"),
  ]);
  const from = typeof company === "string" ? companies.items.find((c) => c.id === company) : undefined;
  return (
    <>
      <PageHeader
        title={from ? `Add a contact at ${from.name}` : "Add a contact"}
        crumbs={from ? [{ href: "/crm/companies", label: "Customers" }, { href: `/crm/companies/${from.id}`, label: from.name }] : [{ href: "/crm/contacts", label: "Contacts" }]}
      />
      <Sheet className="px-5 pt-5 pb-6">
        <ContactForm people={people} companies={companies.items.map((c) => ({ id: c.id, name: c.name }))} companyId={from?.id} layout={fields} />
      </Sheet>
    </>
  );
}
