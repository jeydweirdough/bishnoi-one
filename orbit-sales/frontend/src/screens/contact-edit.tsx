import { notFound } from "next/navigation";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import type { Assignable, CompanyRow, ContactDetail, Paged } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { ContactForm } from "../components/crm/contact-form";
import { formLayout } from "../components/extra/load";

export const metadata = { title: "Edit contact" };

export default async function EditContactPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await getCompanyMe();
  if (!can(me, "customers.edit")) return <NoAccess what="changing customers" />;
  const { id } = await params;
  const [contact, people, companies, fields] = await Promise.all([
    load<ContactDetail>(`/contacts/${enc(id)}`),
    load<Assignable[]>("/people/assignable"),
    load<Paged<CompanyRow>>("/companies?limit=200"),
    formLayout("contact"),
  ]);
  if (!contact.can.edit) notFound();
  return (
    <>
      <PageHeader
        title={`Edit ${contact.name}`}
        crumbs={[
          { href: "/contacts", label: "Contacts" },
          { href: `/contacts/${contact.id}`, label: contact.name },
        ]}
      />
      <Sheet className="px-5 pt-5 pb-6">
        <ContactForm people={people} companies={companies.items.map((c) => ({ id: c.id, name: c.name }))} contact={contact} layout={fields} />
      </Sheet>
    </>
  );
}
