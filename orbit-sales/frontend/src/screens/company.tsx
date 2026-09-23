import { Pencil, Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { PageHeader, Particulars, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Assignable, CustomerType, Paged, Quote, CompanyDetail } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { QuotesPanel } from "../components/quotes-panel";
import { ActivityList } from "../components/crm/activity-list";
import { DeleteRecord } from "../components/crm/list-controls";
import { LogActivity } from "../components/crm/log-activity";
import { StatusTag, siteHref, siteLabel } from "../components/crm/words";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    return { title: (await load<CompanyDetail>(`/companies/${enc(id)}`)).name };
  } catch {
    return { title: "Company" };
  }
}

export default async function CompanyPage({ params }: { params: Params }) {
  const me = await getCompanyMe();
  if (!can(me, "customers.view")) return <NoAccess what="customers" />;
  const { id } = await params;
  const seesQuotes = can(me, "quotes.view");
  const [company, people, quotes, types] = await Promise.all([
    load<CompanyDetail>(`/companies/${enc(id)}`),
    load<Assignable[]>("/people/assignable"),
    seesQuotes ? load<Paged<Quote>>(`/quotes?company=${enc(id)}&limit=20`) : null,
    load<CustomerType[]>("/customer-types"),
  ]);
  const fmt = makeFormat(me.org);
  const mayLog = can(me, "activities.create") && company.can.edit;

  return (
    <>
      <PageHeader
        title={
          <span className="inline-flex flex-wrap items-center gap-2.5">
            {company.name}
            <StatusTag status={company.status} types={types} />
          </span>
        }
        crumbs={[{ href: "/companies", label: "Companies" }]}
        actions={
          <>
            {company.can.edit && (
              <LinkButton href={`/companies/${company.id}/edit`} size="sm" icon={<Pencil className="size-3.5" aria-hidden />}>
                Edit
              </LinkButton>
            )}
            {company.can.delete && (
              <DeleteRecord
                kind="company"
                id={company.id}
                name={company.name}
                body={
                  company.contactCount > 0
                    ? `It has ${company.contactCount} ${company.contactCount === 1 ? "contact" : "contacts"}. Move or delete them first.`
                    : "Its activities are deleted with it. This can't be undone."
                }
              />
            )}
          </>
        }
      >
        {[company.industry, [company.city, company.country].filter(Boolean).join(", ")].filter(Boolean).join(" · ") || "No details yet"}
      </PageHeader>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <div className="space-y-5">
          {mayLog && (
            <Sheet className="px-5 pt-4 pb-5">
              <SectionTitle icon="logActivity">Log or plan</SectionTitle>
              <div className="mt-3">
                <LogActivity org={me.org} now={new Date().toISOString()} people={people} companyId={company.id} contacts={company.contacts.map((c) => ({ id: c.id, name: c.name }))} />
              </div>
            </Sheet>
          )}
          {quotes && (
            <Sheet className="px-5 pt-4 pb-3">
              <SectionTitle icon="quotes">Quotes{quotes.total > quotes.items.length ? ` (latest ${quotes.items.length} of ${quotes.total})` : ""}</SectionTitle>
              <QuotesPanel customerHref={`/companies/${company.id}`} quotes={quotes.items} canAdd={can(me, "quotes.create")} showWho />
            </Sheet>
          )}
          <Sheet className="px-5 pt-4 pb-2">
            <SectionTitle icon="history">Activity</SectionTitle>
            <ActivityList
              activities={company.activities}
              org={me.org}
              hide={["company"]}
              empty="Nothing yet. Calls, meetings, emails, notes and tasks about this company show up here."
            />
          </Sheet>
        </div>

        <div className="space-y-5">
          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle icon="particulars">Details</SectionTitle>
            <div className="mt-3">
              <Particulars
                items={[
                  ["Owner", company.owner.id === me.user.id ? "You" : company.owner.name],
                  ["Team", company.team?.name ?? null],
                  ["Phone", company.phone ? <a href={`tel:${company.phone}`} className="text-hema hover:underline">{company.phone}</a> : null],
                  ["Email", company.email ? <a href={`mailto:${company.email}`} className="text-hema hover:underline">{company.email}</a> : null],
                  ["Website", company.website ? <a href={siteHref(company.website)} target="_blank" rel="noopener noreferrer" className="text-hema hover:underline">{siteLabel(company.website)}</a> : null],
                  ["Address", company.address],
                  ["Added", fmt.whenLabel(company.createdAt)],
                ]}
              />
              {company.notes && <p className="mt-4 border-t border-rule pt-3 text-sm whitespace-pre-line text-ink-2">{company.notes}</p>}
            </div>
          </Sheet>

          <Sheet className="px-5 pt-4 pb-3">
            <SectionTitle
              icon="customers"
              action={
                can(me, "customers.create") && (
                  <LinkButton href={`/contacts/new?company=${company.id}`} size="sm" variant="quiet" icon={<Plus className="size-3.5" aria-hidden />}>
                    Add
                  </LinkButton>
                )
              }
            >
              Contacts
            </SectionTitle>
            {company.contacts.length === 0 ? (
              <p className="py-2 text-meta text-ink-3">No contacts yet.</p>
            ) : (
              <ul className="mt-1 divide-y divide-rule">
                {company.contacts.map((c) => (
                  <li key={c.id} className="py-2.5">
                    <Link href={`/contacts/${c.id}`} className="font-medium text-hema hover:underline">
                      {c.name}
                    </Link>
                    <p className="text-meta text-ink-3">{[c.jobTitle, c.email ?? c.phone].filter(Boolean).join(" · ") || "No details"}</p>
                  </li>
                ))}
              </ul>
            )}
            {company.contactCount > company.contacts.length && (
              <p className="pt-2 text-meta text-ink-3">
                {company.contactCount - company.contacts.length} more belong to other people.
              </p>
            )}
          </Sheet>
        </div>
      </div>
    </>
  );
}
