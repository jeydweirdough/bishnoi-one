import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Assignable, CustomerType, DealList, Paged, Quote, CompanyDetail } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { AssociationsPanel } from "../components/crm/associations-panel";
import { loadRecord } from "../components/crm/merged";
import { QuotesPanel } from "../components/quotes-panel";
import { formLayout } from "../components/extra/load";
import { layoutForTeam } from "../components/extra/teams";
import { DetailSections } from "../components/crm/detail-sections";
import { ProgressRing } from "../components/progress-ring";
import type { ReactNode } from "react";
import { layoutItems } from "../components/extra/extra-values";
import { ActivityList } from "../components/crm/activity-list";
import { DeleteRecord, EditRecord } from "../components/crm/list-controls";
import { LogActivityButton } from "../components/crm/log-activity-button";
import { NewCallButton } from "../components/crm/new-call";
import { EmailButton } from "../components/mailbox/email-button";
import { Icon } from "@/src/platform/ui/icons";
import type { CrmKind } from "@/src/platform/lib/types";
import { RecordTabs } from "../components/crm/record-tabs";
import { TransferCustomer } from "../components/crm/transfer-customer";
import { StatusTag, siteHref, siteLabel } from "../components/crm/words";
import { StageTag } from "../components/deals/words";
import { ClinicPin } from "../components/field/clinic-pin";
import { LogVisitButton } from "../components/field/log-visit";
import type { DoctorBalance, Visit } from "../components/field/types";
import { VisitList } from "../components/field/visit-list";
import { isFieldAgent } from "../components/field/words";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    return { title: (await load<CompanyDetail>(`/companies/${enc(id)}`)).name };
  } catch {
    return { title: "Customer" };
  }
}

// The customer page's quick actions, under the name.
// Email is its own (sent from the person's mailbox), second in the row.
const QUICK: { kind: CrmKind; label: string; icon: "note" | "email" | "call" | "task" | "visit" }[] = [
  { kind: "note", label: "Note", icon: "note" },
  { kind: "call", label: "Call", icon: "call" },
  { kind: "task", label: "Task", icon: "task" },
  { kind: "meeting", label: "Meeting", icon: "visit" },
];

export default async function CompanyPage({ params, searchParams }: { params: Params; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  if (!can(me, "customers.view")) return <NoAccess what="customers" />;
  const { id } = await params;
  const seesQuotes = can(me, "quotes.view");
  const seesVisits = can(me, "visits.view");
  const seesDeals = can(me, "deals.view");
  const [company, people, quotes, types, fields, visits, owed, deals] = await Promise.all([
    loadRecord<CompanyDetail>("companies", id),
    load<Assignable[]>("/people/assignable"),
    seesQuotes ? load<Paged<Quote>>(`/quotes?company=${enc(id)}&limit=20`) : null,
    load<CustomerType[]>("/customer-types"),
    formLayout("company"),
    seesVisits ? load<Paged<Visit>>(`/visits?company=${enc(id)}&limit=30`) : null,
    seesVisits ? load<DoctorBalance>(`/field/doctors/${enc(id)}`) : null,
    seesDeals ? load<DealList>(`/deals?company=${enc(id)}&limit=10`) : null,
  ]);
  const fmt = makeFormat(me.org);
  const mayLog = can(me, "activities.create") && company.can.edit;
  const asked = (await searchParams).tab;
  const tab = asked === "quotes" && quotes ? "quotes" : asked === "visits" && visits ? "visits" : "activity";
  const mayVisit = can(me, "visits.create") && company.can.edit;
  const isDoctor = company.status === "doctor" || !!owed?.balance;

  // The form this customer has (its division's, for its type), and how much of
  // its profile is filled in: the fields an administrator added to it.
  const ownForm = layoutForTeam(fields, company.team?.id ?? null, company.status);
  const profileFields = ownForm.sections.flatMap((s) => s.fields).filter((f) => !f.standard);
  const profileFilled = profileFields.filter((f) => {
    const v = company.extra?.[f.key];
    return v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && v.length === 0);
  }).length;
  const profile = { total: profileFields.length, pct: profileFields.length ? Math.round((100 * profileFilled) / profileFields.length) : 0 };

  // How built-in details read on this page: links, and Transfer beside who it's assigned to.
  const shownDetails: Record<string, ReactNode> = {
    // Fields that point at another customer (its hospital): its name, a link when one may open it.
    ...Object.fromEntries(
      Object.entries(company.links ?? {}).map(([key, l]) => [
        key,
        l.canOpen ? (
          <Link href={`/companies/${l.id}`} className="text-ink hover:underline">
            {l.name}
          </Link>
        ) : (
          <span>
            {l.name}
            {l.teamName && <span className="text-ink-3"> · {l.teamName}</span>}
          </span>
        ),
      ]),
    ),
    ownerId: (
      <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1">
        {company.owner.id === me.user.id ? "You" : company.owner.name}
        {company.can.edit && <TransferCustomer companyId={company.id} companyName={company.name} />}
      </span>
    ),
    phone: company.phone ? <a href={`tel:${company.phone}`} className="text-ink hover:underline">{company.phone}</a> : null,
    email: company.email ? <a href={`mailto:${company.email}`} className="text-ink hover:underline">{company.email}</a> : null,
    website: company.website ? (
      <a href={siteHref(company.website)} target="_blank" rel="noopener noreferrer" className="text-ink hover:underline">
        {siteLabel(company.website)}
      </a>
    ) : null,
  };

  return (
    <>
      <PageHeader
        title={
          <span className="inline-flex flex-wrap items-center gap-2.5">
            {company.name}
            <StatusTag status={company.status} types={types} />
            {company.code && <span className="font-mono text-sm font-normal text-ink-3">{company.code}</span>}
          </span>
        }
        // Edit and delete act on the customer itself, so they sit with its name.
        tools={
          <>
            {company.can.edit && <EditRecord href={`/companies/${company.id}/edit`} what="customer" />}
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
        crumbs={[{ href: "/companies", label: "Customers" }]}
        actions={
          <>
            {/* The one solid button: what a customer's page is most often opened to do. */}
            {can(me, "quotes.create") && (
              <LinkButton href={`/companies/${company.id}/quotes/new`} variant="primary" icon={<Plus className="size-4" aria-hidden />}>
                New quote
              </LinkButton>
            )}
            {/* A field agent's page for a doctor: the visit is what it's opened for. */}
            {mayVisit && (
              <LogVisitButton
                requireLocation={isFieldAgent(me)}
                variant={can(me, "quotes.create") ? "default" : "primary"}
                org={me.org}
                now={new Date().toISOString()}
                doctor={{ id: company.id, name: company.name }}
              />
            )}
          </>
        }
      >
        {[company.industry, [company.city, company.country].filter(Boolean).join(", "), company.leadSource && `Lead source: ${company.leadSource}`]
          .filter(Boolean)
          .join(" · ") || "No details yet"}
      </PageHeader>

      {/* Three columns (HubSpot's record page): who they are and what to do; what's happened; what they're linked to. */}
      <div className="grid gap-5 lg:grid-cols-[18rem_minmax(0,1fr)] lg:items-start xl:grid-cols-[18rem_minmax(0,1fr)_20rem]">
        <div className="space-y-5">
          <Sheet className="px-4 py-4">
            {/* What's done most on a customer, one click from their name. */}
            <div className="flex flex-wrap justify-between gap-y-3">
              {mayLog &&
                QUICK.map((q, n) => [
                  n === 1 && (
                    <EmailButton key="email" companyId={company.id} companyName={company.name} />
                  ),
                  <LogActivityButton
                    key={q.kind}
                    kind={q.kind}
                    label={q.label}
                    quick={<Icon name={q.icon} className="size-4" />}
                    org={me.org}
                    now={new Date().toISOString()}
                    people={people}
                    companyId={company.id}
                    contacts={company.contacts.map((c) => ({ id: c.id, name: c.name }))}
                  />,
                ])}
            </div>
            <div className="mt-4 flex flex-wrap gap-2 border-t border-rule pt-3">
              {mayLog && <NewCallButton variant="default" customer={{ id: company.id, name: company.name }} />}
              <LinkButton href={`/media?for=${company.id}`}>Materials</LinkButton>
            </div>
          </Sheet>
          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle
              icon="particulars"
              action={
                profile.total > 0 && (
                  <span className="flex items-center gap-2">
                    <ProgressRing size="xs" pct={profile.pct} tone={profile.pct === 100 ? "good" : "plain"} label={`Profile ${profile.pct}% complete`} />
                    {profile.pct < 100 && company.can.edit && (
                      <LinkButton href={`/companies/${company.id}/edit?complete=1`} size="sm">
                        Complete profile
                      </LinkButton>
                    )}
                  </span>
                )
              }
            >
              Details
            </SectionTitle>
            <div className="mt-2">
              <DetailSections
                sections={ownForm.sections.map((section, i, all) => ({
                  title: section.title,
                  items: [
                    // The system's code for it heads the first section.
                    ...(i === 0 ? ([["Customer code", company.code]] as [string, ReactNode][]) : []),
                    ...layoutItems(fmt, section.fields, company, shownDetails, ["name", "status", "notes"]),
                    // Team and when it was added go with who it's assigned to (or last).
                    ...((section.fields.some((f) => f.key === "ownerId") || (i === all.length - 1 && !all.some((x) => x.fields.some((f) => f.key === "ownerId"))))
                      ? ([["Team", company.team?.name ?? null], ["Added", fmt.whenLabel(company.createdAt)]] as [string, ReactNode][])
                      : []),
                  ],
                })).filter((section) => section.items.length > 0)}
              />
              {company.notes && <p className="mt-4 border-t border-rule pt-3 text-sm whitespace-pre-line text-ink-2">{company.notes}</p>}
            </div>
          </Sheet>

        </div>

        <div className="min-w-0 space-y-5">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Open deals", deals ? fmt.peso(deals.items.filter((d) => d.state === "open").reduce((t, d) => t + d.valueCentavos, 0)) : "—"],
              ["Quotes", quotes ? String(quotes.total) : "—"],
              ["Last activity", company.lastActivityAt ? fmt.whenLabel(company.lastActivityAt) : "None yet"],
              ["Profile", profile.total ? `${profile.pct}%` : "—"],
            ].map(([label, value]) => (
              <Sheet key={label} className="px-4 py-3">
                <p className="text-meta text-ink-3">{label}</p>
                <p className="mt-0.5 truncate font-semibold text-ink">{value}</p>
              </Sheet>
            ))}
          </div>
          <Sheet className="px-5 pb-2">
            <RecordTabs
              base={`/companies/${company.id}`}
              current={tab}
              tabs={[
                { key: "activity", label: "Activity", count: company.activities.length },
                ...(quotes ? [{ key: "quotes", label: "Quotes", count: quotes.total }] : []),
                ...(visits && (isDoctor || visits.total) ? [{ key: "visits", label: "Visits", count: visits.total }] : []),
              ]}
            />
            {tab === "visits" && visits ? (
              visits.items.length ? (
                <VisitList visits={visits.items} fmt={fmt} today={fmt.todayKey()} showDoctor={false} />
              ) : (
                <p className="py-6 text-center text-meta text-ink-3">No visits yet. Use Log visit after each one.</p>
              )
            ) : tab === "quotes" && quotes ? (
              <>
                <QuotesPanel customerHref={`/companies/${company.id}`} quotes={quotes.items} canAdd={false} showWho />
                {quotes.total > quotes.items.length && (
                  <Link href={`/quotes?q=${encodeURIComponent(company.name)}`} className="block py-2 text-meta text-ink hover:underline">
                    See all {quotes.total}
                  </Link>
                )}
              </>
            ) : (
              <ActivityList
                activities={company.activities}
                org={me.org}
                hide={["company"]}
                empty="Nothing yet. Calls, meetings, emails, notes and tasks about this customer show up here: use Log activity."
              />
            )}
          </Sheet>
        </div>

        <div className="space-y-5 lg:col-span-2 xl:col-span-1">
          <AssociationsPanel kind="company" id={company.id} />
          {deals && (
            <Sheet className="px-5 pt-4 pb-3">
              <SectionTitle
                icon="deals"
                action={
                  can(me, "deals.create") &&
                  company.can.edit && (
                    <LinkButton href={`/deals/new?company=${company.id}`} size="sm" variant="quiet" icon={<Plus className="size-3.5" aria-hidden />}>
                      Add
                    </LinkButton>
                  )
                }
              >
                Deals
              </SectionTitle>
              {deals.items.length === 0 ? (
                <p className="py-2 text-meta text-ink-3">No deals yet. Add one to forecast what this customer may buy.</p>
              ) : (
                <ul className="mt-1 divide-y divide-rule">
                  {deals.items.map((d) => (
                    <li key={d.id} className="py-2.5">
                      <span className="flex items-start justify-between gap-2">
                        <Link href={`/deals/${d.id}`} className="min-w-0 font-medium text-ink hover:underline">
                          {d.name}
                        </Link>
                        <StageTag deal={d} />
                      </span>
                      <p className="text-meta text-ink-3">
                        {fmt.peso(d.valueCentavos)} · {d.state === "open" ? `closes ${fmt.dateLabel(d.expectedCloseOn)}` : `closed ${fmt.dateLabel(d.expectedCloseOn)}`}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
              {deals.total > deals.items.length && (
                <Link href={`/deals?view=list&q=${encodeURIComponent(company.name)}`} className="block pt-2 text-meta text-ink hover:underline">
                  See all {deals.total}
                </Link>
              )}
            </Sheet>
          )}

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
                    <Link href={`/contacts/${c.id}`} className="font-medium text-ink hover:underline">
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
          {owed && isDoctor && (
            <Sheet className="px-5 pt-4 pb-5">
              <SectionTitle icon="money">Owes</SectionTitle>
              {owed.balance ? (
                <>
                  <p className="mt-2 text-figure text-ink">{fmt.peso(owed.balance.owedCentavos)}</p>
                  <p className="mt-1 text-meta text-ink-3">
                    {fmt.peso(owed.balance.balanceCentavos)} as of {fmt.dateLabel(owed.balance.asOf)}
                    {owed.balance.collectedSinceCentavos > 0 && <>, less {fmt.peso(owed.balance.collectedSinceCentavos)} collected since</>}
                  </p>
                </>
              ) : (
                <p className="mt-2 text-meta text-ink-3">No balance on file yet. It comes from accounting&apos;s upload.</p>
              )}
            </Sheet>
          )}
          {owed && isDoctor && (
            <ClinicPin
              companyId={company.id}
              pin={owed.pin}
              canPin={owed.can.pin}
              canUnpin={owed.can.unpin}
              pinnedOn={owed.pin?.pinnedAt ? fmt.whenLabel(owed.pin.pinnedAt) : null}
            />
          )}
        </div>
      </div>
    </>
  );
}
