import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { Assignable, CompanyRow, Paged } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { ContactForm } from "../components/crm/contact-form";

export const metadata = { title: "Add a contact" };

type Search = Promise<Record<string, string | string[] | undefined>>;

export default async function NewContactPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "customers.create")) return <NoAccess what="adding customers" />;
  const { company } = await searchParams;
  const [people, companies] = await Promise.all([
    load<Assignable[]>("/people/assignable"),
    load<Paged<CompanyRow>>("/companies?limit=200"),
  ]);
  const from = typeof company === "string" ? companies.items.find((c) => c.id === company) : undefined;
  return (
    <>
      <PageHeader
        title={from ? `Add a contact at ${from.name}` : "Add a contact"}
        crumbs={from ? [{ href: "/companies", label: "Companies" }, { href: `/companies/${from.id}`, label: from.name }] : [{ href: "/contacts", label: "Contacts" }]}
      />
      <Sheet className="px-5 pt-5 pb-6">
        <ContactForm people={people} companies={companies.items.map((c) => ({ id: c.id, name: c.name }))} companyId={from?.id} />
      </Sheet>
    </>
  );
}
