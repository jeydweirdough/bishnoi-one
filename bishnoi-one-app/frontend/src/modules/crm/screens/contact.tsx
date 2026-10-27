import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { PageHeader, Particulars, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Assignable, Paged, Quote, ContactDetail } from "@/src/platform/lib/types";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { AssociationsPanel } from "@/src/modules/crm/components/crm/associations-panel";
import { loadRecord } from "@/src/modules/crm/components/crm/merged";
import { QuotesPanel } from "@/src/modules/crm/components/quotes-panel";
import { formLayout, layoutFields } from "@/src/modules/crm/components/extra/load";
import { layoutItems } from "@/src/modules/crm/components/extra/extra-values";
import { ActivityList } from "@/src/modules/crm/components/crm/activity-list";
import { DeleteRecord, EditRecord } from "@/src/modules/crm/components/crm/list-controls";
import { LogActivityButton } from "@/src/modules/crm/components/crm/log-activity-button";
import { RecordTabs } from "@/src/modules/crm/components/crm/record-tabs";
import { CopyButton } from "@/src/platform/ui/copy-button";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    return { title: (await load<ContactDetail>(`/contacts/${enc(id)}`)).name };
  } catch {
    return { title: "Contact" };
  }
}

export default async function ContactPage({ params, searchParams }: { params: Params; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  if (!can(me, "customers.view")) return <NoAccess what="customers" />;
  const { id } = await params;
  const seesQuotes = can(me, "quotes.view");
  const [contact, people, quotes, fields] = await Promise.all([
    loadRecord<ContactDetail>("contacts", id),
    load<Assignable[]>("/people/assignable"),
    seesQuotes ? load<Paged<Quote>>(`/quotes?contact=${enc(id)}&limit=20`) : null,
    formLayout("contact"),
  ]);
  const fmt = makeFormat(me.org);
  const mayLog = can(me, "activities.create") && contact.can.edit;
  const tab = (await searchParams).tab === "quotes" && quotes ? "quotes" : "activity";
  const link = (href: string, text: string) => (
    <span className="inline-flex min-w-0 items-center gap-1">
      <a href={href} className="truncate text-ink hover:underline">
        {text}
      </a>
      <CopyButton text={text} what={href.startsWith("mailto:") ? "Email" : "Phone number"} />
    </span>
  );

  return (
    <>
      <PageHeader
        title={contact.name}
        // Edit and delete act on the contact itself, so they sit with its name.
        tools={
          <>
            {contact.can.edit && <EditRecord href={`/crm/contacts/${contact.id}/edit`} what="contact" />}
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
        crumbs={[{ href: "/crm/contacts", label: "Contacts" }]}
        actions={
          <>
            {/* The one solid button: what a customer's page is most often opened to do. */}
            {can(me, "quotes.create") && (
              <LinkButton href={`/crm/contacts/${contact.id}/quotes/new`} variant="primary" icon={<Plus className="size-4" aria-hidden />}>
                New quote
              </LinkButton>
            )}
            {mayLog && <LogActivityButton org={me.org} now={new Date().toISOString()} people={people} contactId={contact.id} companyId={contact.company?.id} />}
          </>
        }
      >
        {contact.jobTitle}
        {contact.jobTitle && contact.company ? " at " : ""}
        {contact.company ? (
          <Link href={`/crm/customers/${contact.company.id}`} className="text-ink hover:underline">
            {contact.company.name}
          </Link>
        ) : (
          !contact.jobTitle && "No customer"
        )}
      </PageHeader>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <Sheet className="px-5 pb-2">
          <RecordTabs
            base={`/crm/contacts/${contact.id}`}
            current={tab}
            tabs={[
              { key: "activity", label: "Activity", count: contact.activities.length },
              ...(quotes ? [{ key: "quotes", label: "Quotes", count: quotes.total }] : []),
            ]}
          />
          {tab === "quotes" && quotes ? (
            <QuotesPanel customerHref={`/crm/contacts/${contact.id}`} quotes={quotes.items} canAdd={false} />
          ) : (
            <ActivityList
              activities={contact.activities}
              org={me.org}
              hide={["contact"]}
              empty="Nothing yet. Calls, meetings, emails, notes and tasks with them show up here: use Log activity."
            />
          )}
        </Sheet>

        <div className="space-y-5">
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="particulars">Details</SectionTitle>
          <div className="mt-3">
            <Particulars
              items={[
                ...layoutItems(
                  fmt,
                  layoutFields(fields),
                  contact,
                  {
                    email: contact.email ? link(`mailto:${contact.email}`, contact.email) : null,
                    phone: contact.phone ? link(`tel:${contact.phone}`, contact.phone) : null,
                    mobile: contact.mobile ? link(`tel:${contact.mobile}`, contact.mobile) : null,
                    ownerId: contact.owner.id === me.user.id ? "You" : contact.owner.name,
                  },
                  // Already on the page: the name and title in the header, the notes under these.
                  ["firstName", "lastName", "jobTitle", "companyId", "notes"],
                ),
                ["Team", contact.team?.name ?? null],
                ["Added", fmt.whenLabel(contact.createdAt)],
              ]}
            />
            {contact.notes && <p className="mt-4 border-t border-rule pt-3 text-sm whitespace-pre-line text-ink-2">{contact.notes}</p>}
          </div>
        </Sheet>
        <AssociationsPanel kind="contact" id={contact.id} />
        </div>
      </div>
    </>
  );
}
