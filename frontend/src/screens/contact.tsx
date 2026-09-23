import { Pencil } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { PageHeader, Particulars, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Assignable, Paged, Quote, ContactDetail } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { QuotesPanel } from "../components/quotes-panel";
import { ActivityList } from "../components/crm/activity-list";
import { DeleteRecord } from "../components/crm/list-controls";
import { LogActivity } from "../components/crm/log-activity";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    return { title: (await load<ContactDetail>(`/contacts/${enc(id)}`)).name };
  } catch {
    return { title: "Contact" };
  }
}

export default async function ContactPage({ params }: { params: Params }) {
  const me = await getCompanyMe();
  if (!can(me, "customers.view")) return <NoAccess what="customers" />;
  const { id } = await params;
  const seesQuotes = can(me, "quotes.view");
  const [contact, people, quotes] = await Promise.all([
    load<ContactDetail>(`/contacts/${enc(id)}`),
    load<Assignable[]>("/people/assignable"),
    seesQuotes ? load<Paged<Quote>>(`/quotes?contact=${enc(id)}&limit=20`) : null,
  ]);
  const fmt = makeFormat(me.org);
  const mayLog = can(me, "activities.create") && contact.can.edit;
  const link = (href: string, text: string) => (
    <a href={href} className="text-hema hover:underline">
      {text}
    </a>
  );

  return (
    <>
      <PageHeader
        title={contact.name}
        crumbs={[{ href: "/contacts", label: "Contacts" }]}
        actions={
          <>
            {contact.can.edit && (
              <LinkButton href={`/contacts/${contact.id}/edit`} size="sm" icon={<Pencil className="size-3.5" aria-hidden />}>
                Edit
              </LinkButton>
            )}
            {contact.can.delete && (
              <DeleteRecord
                kind="contact"
                id={contact.id}
                name={contact.name}
                body={
                  contact.company
                    ? `Activities about them stay with ${contact.company.name}. This can't be undone.`
                    : "Activities about them are deleted with them. This can't be undone."
                }
              />
            )}
          </>
        }
      >
        {contact.jobTitle}
        {contact.jobTitle && contact.company ? " at " : ""}
        {contact.company ? (
          <Link href={`/companies/${contact.company.id}`} className="text-hema hover:underline">
            {contact.company.name}
          </Link>
        ) : (
          !contact.jobTitle && "No company"
        )}
      </PageHeader>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <div className="space-y-5">
          {mayLog && (
            <Sheet className="px-5 pt-4 pb-5">
              <SectionTitle icon="logActivity">Log or plan</SectionTitle>
              <div className="mt-3">
                <LogActivity org={me.org} now={new Date().toISOString()} people={people} contactId={contact.id} companyId={contact.company?.id} />
              </div>
            </Sheet>
          )}
          {quotes && (
            <Sheet className="px-5 pt-4 pb-3">
              <SectionTitle icon="quotes">Quotes{quotes.total > quotes.items.length ? ` (latest ${quotes.items.length} of ${quotes.total})` : ""}</SectionTitle>
              <QuotesPanel customerHref={`/contacts/${contact.id}`} quotes={quotes.items} canAdd={can(me, "quotes.create")} />
            </Sheet>
          )}
          <Sheet className="px-5 pt-4 pb-2">
            <SectionTitle icon="history">Activity</SectionTitle>
            <ActivityList
              activities={contact.activities}
              org={me.org}
              hide={["contact"]}
              empty="Nothing yet. Calls, meetings, emails, notes and tasks with them show up here."
            />
          </Sheet>
        </div>

        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="particulars">Details</SectionTitle>
          <div className="mt-3">
            <Particulars
              items={[
                ["Email", contact.email ? link(`mailto:${contact.email}`, contact.email) : null],
                ["Phone", contact.phone ? link(`tel:${contact.phone}`, contact.phone) : null],
                ["Mobile", contact.mobile ? link(`tel:${contact.mobile}`, contact.mobile) : null],
                ["Owner", contact.owner.id === me.user.id ? "You" : contact.owner.name],
                ["Team", contact.team?.name ?? null],
                ["Added", fmt.whenLabel(contact.createdAt)],
              ]}
            />
            {contact.notes && <p className="mt-4 border-t border-rule pt-3 text-sm whitespace-pre-line text-ink-2">{contact.notes}</p>}
          </div>
        </Sheet>
      </div>
    </>
  );
}
