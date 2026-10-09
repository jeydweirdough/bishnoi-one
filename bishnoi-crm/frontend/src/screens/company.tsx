import { OrderLinkButton } from "../components/quotes/order-link-button";
import { Plus, Search } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { api, enc, getCompanyMe, query } from "@/src/platform/lib/api";
import { notFound, redirect } from "next/navigation";
import { cache } from "react";
import { makeFormat } from "@/src/platform/lib/format";
import type { Assignable, CustomerType, DealList, FormLayout, Paged, Quote, CompanyDetail } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { AssociationsPanel } from "../components/crm/associations-panel";
import { QuotesPanel } from "../components/quotes-panel";
import { layoutForTeam } from "../components/extra/teams";
import { DetailSections } from "../components/crm/detail-sections";
import { EmptyArt } from "../components/crm/empty-art";
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
import { lower, termsOf } from "../components/terms/terms";

type Params = Promise<{ id: string }>;

// The customer page's one request: the customer, the lists its forms pick
// from, and its quotes, visits and deals when the person may see them.
const CUSTOMER = `query Customer($id: String!, $quotes: Boolean!, $visits: Boolean!, $deals: Boolean!) {
  company(id: $id) {
    id code name status priceGroupCode industry leadSource website email phone city country
    owner { id name } team { id name } contactCount lastActivityAt updatedAt extra can { edit delete }
    address notes createdAt links linkedHere contacts { id name jobTitle email phone } activities
  }
  people { id name isMe team { id name } }
  customerTypes { code name color sortOrder isActive companies onlyTeams exceptTeams }
  form(entity: "company")
  quotes(company: $id, limit: 20) @include(if: $quotes)
  visits(company: $id, limit: 30) @include(if: $visits)
  doctorBalance(companyId: $id) @include(if: $visits)
  deals(company: $id, limit: 10) @include(if: $deals)
}`;
type CustomerAnswer = {
  company: CompanyDetail | null;
  people: Assignable[] | null;
  customerTypes: CustomerType[] | null;
  form: FormLayout | null;
  quotes?: Paged<Quote> | null;
  visits?: Paged<Visit> | null;
  doctorBalance?: DoctorBalance | null;
  deals?: DealList | null;
};

/** Read once per render: the tab's title and the page share it (plain arguments, so the cache matches). */
const customerPage = cache(async (id: string, quotes: boolean, visits: boolean, deals: boolean) => {
  const { data, errors } = await query<CustomerAnswer>(CUSTOMER, { id, quotes, visits, deals });
  if (data.company) return data as CustomerAnswer & { company: CompanyDetail };
  const why = errors.find((e) => e.path?.[0] === "company")?.extensions?.status;
  if (why !== 404) throw new Error(errors[0]?.message ?? "The customer couldn't be read.");
  // Merged into another customer: its old links lead to the one kept.
  const merged = await api.get<{ newId: string }>(`/merged/${enc(id)}`).catch(() => null);
  if (merged) redirect(`/companies/${merged.newId}`);
  notFound();
});

const pageFor = (me: Awaited<ReturnType<typeof getCompanyMe>>, id: string) => customerPage(id, can(me, "quotes.view"), can(me, "visits.view"), can(me, "deals.view"));

export async function generateMetadata({ params }: { params: Params }) {
  const { id } = await params;
  try {
    const me = await getCompanyMe();
    return { title: (await pageFor(me, id)).company.name };
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
  const answer = await pageFor(me, id);
  const { company } = answer;
  const people = answer.people ?? [];
  const types = answer.customerTypes ?? [];
  const fields = answer.form ?? { entity: "company" as const, sections: [] };
  const quotes = answer.quotes ?? null;
  const visits = answer.visits ?? null;
  const owed = answer.doctorBalance ?? null;
  const deals = answer.deals ?? null;
  const fmt = makeFormat(me.org);
  const mayLog = can(me, "activities.create") && company.can.edit;
  const asked = (await searchParams).tab;
  const tab = asked === "quotes" && quotes ? "quotes" : asked === "visits" && visits ? "visits" : "activity";
  const mayVisit = can(me, "visits.create") && company.can.edit;
  // Someone field agents visit (Settings → Terms): the customer type they are, or anyone with a balance.
  const isDoctor = (!!termsOf(me).visitedType && company.status === termsOf(me).visitedType) || !!owed?.balance;

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

  const terms = termsOf(me);
  const openDeals = deals ? deals.items.filter((d) => d.state === "open") : [];
  const initials = company.name
    .replace(/^(dr|dra)\.?\s+/i, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
  const place = [company.industry, [company.city, company.country].filter(Boolean).join(", "), `assigned to ${company.owner.id === me.user.id ? "you" : company.owner.name}`]
    .filter(Boolean)
    .join(" · ");
  const facts: [string, ReactNode][] = [
    ["Last activity", company.lastActivityAt ? fmt.whenLabel(company.lastActivityAt) : "None yet"],
    ...(deals ? ([["Open deals", openDeals.length ? `${openDeals.length} · ${fmt.peso(openDeals.reduce((t, d) => t + d.valueCentavos, 0))}` : "None"]] as [string, ReactNode][]) : []),
    ...(quotes ? ([["Quotes", String(quotes.total)]] as [string, ReactNode][]) : []),
    ["Contacts", String(company.contactCount)],
    ...(isDoctor && owed ? ([["Owes", owed.balance ? fmt.peso(owed.balance.owedCentavos) : "Nothing on file"]] as [string, ReactNode][]) : []),
  ];
  const logProps = {
    org: me.org,
    now: new Date().toISOString(),
    people,
    companyId: company.id,
    contacts: company.contacts.map((c) => ({ id: c.id, name: c.name })),
  };

  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-3 text-meta">
        <Link href="/companies" className="text-ink-2 underline-offset-2 hover:text-ink hover:underline">
          Customers
        </Link>
      </nav>

      {/* Who they are, where things stand, and what to do: one card, as on the components page. */}
      <section aria-labelledby="customer-name" className="mb-5 rounded-[22px] border-[1.5px] border-ink bg-sheet px-5 pt-5 pb-4 sm:px-6">
        <div className="flex flex-wrap items-start gap-x-5 gap-y-4">
          <span className="grid size-14 shrink-0 place-items-center rounded-full border-[1.5px] border-ink bg-sage text-lg font-semibold text-ink" aria-hidden>
            {initials || "?"}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
              <h1 id="customer-name" className="text-title text-ink">
                {company.name}
              </h1>
              {company.code && <span className="rounded-[8px] bg-[#f3f3f1] px-2 py-0.5 text-meta font-medium tracking-wide text-ink-2">{company.code}</span>}
              {/* Edit and delete act on the customer itself, so they sit with its name. */}
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
            </div>
            <p className="mt-1 text-sm text-ink-3">{place}</p>
            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
              <StatusTag status={company.status} types={types} />
              {company.leadSource && (
                <span className="inline-flex h-6 items-center rounded-full bg-[#f0f0ee] px-2.5 text-meta font-medium text-ink-2">From {lower(company.leadSource)}</span>
              )}
            </div>
          </div>
          {/* The one solid button: what a customer's page is most often opened to do. */}
          <div className="flex flex-wrap items-center gap-2">
            {mayVisit && (
              <LogVisitButton
                requireLocation={isFieldAgent(me)}
                variant={isDoctor ? "primary" : "default"}
                org={me.org}
                now={new Date().toISOString()}
                doctor={{ id: company.id, name: company.name }}
              />
            )}
            {can(me, "quotes.create") && (
              <>
                {/* The medicine search: a quick quote here, or a link for the customer to order from. */}
                <OrderLinkButton companyId={company.id} companyName={company.name} slug={me.org.slug} />
                <LinkButton href={`/companies/${company.id}/quotes/quick`} icon={<Search className="size-4" aria-hidden />}>
                  Quick quote
                </LinkButton>
                <LinkButton href={`/companies/${company.id}/quotes/new`} variant={mayVisit && isDoctor ? "default" : "primary"} icon={<Plus className="size-4" aria-hidden />}>
                  New quote
                </LinkButton>
              </>
            )}
          </div>
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-rule pt-4 sm:grid-cols-3 lg:grid-cols-[repeat(5,minmax(0,1fr))]">
          {facts.map(([label, value]) => (
            <div key={label} className="min-w-0">
              <dt className="text-meta text-ink-3">{label}</dt>
              <dd className="mt-0.5 truncate text-sm font-semibold text-ink">{value}</dd>
            </div>
          ))}
          {profile.total > 0 && (
            <div className="flex min-w-0 items-center gap-2.5">
              <ProgressRing size="xs" pct={profile.pct} tone={profile.pct === 100 ? "good" : "plain"} label={`Profile ${profile.pct}% complete`} />
              <div className="min-w-0">
                <dt className="text-meta text-ink-3">Profile</dt>
                <dd className="text-sm">
                  {profile.pct < 100 && company.can.edit ? (
                    <Link href={`/companies/${company.id}/edit?complete=1`} className="font-semibold text-sage-deep hover:underline">
                      Complete it
                    </Link>
                  ) : (
                    <span className="font-semibold text-ink">Complete</span>
                  )}
                </dd>
              </div>
            </div>
          )}
        </dl>

        {/* What's done most on a customer, one click from their name. */}
        {mayLog && (
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-rule pt-4">
            <span className="mr-1 text-meta text-ink-3">Log</span>
            {QUICK.map((q, n) => [
              n === 1 && <EmailButton key="email" companyId={company.id} companyName={company.name} />,
              <LogActivityButton key={q.kind} kind={q.kind} label={q.label} quick={<Icon name={q.icon} className="size-4" />} {...logProps} />,
            ])}
            <span className="mx-1 h-5 w-px bg-rule" aria-hidden />
            <NewCallButton variant="default" customer={{ id: company.id, name: company.name }} />
            <LinkButton href={`/media?for=${company.id}`} variant="quiet">
              Materials
            </LinkButton>
          </div>
        )}
      </section>

      {/* Two columns: what's happened, wide; who they are and what they're linked to, beside it. */}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
        <div className="min-w-0 space-y-5">
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
                <VisitList visits={visits.items} fmt={fmt} today={fmt.todayKey()} showDoctor={false} site={lower(terms.site)} />
              ) : (
                <EmptyArt art="calendar" title="No visits yet">
                  Log each visit after it, so your Team Lead sees it and the next one starts from where this one ended.
                </EmptyArt>
              )
            ) : tab === "quotes" && quotes ? (
              quotes.items.length ? (
                <>
                  <QuotesPanel customerHref={`/companies/${company.id}`} quotes={quotes.items} canAdd={false} showWho />
                  {quotes.total > quotes.items.length && (
                    <Link href={`/quotes?q=${encodeURIComponent(company.name)}`} className="block py-2 text-meta text-ink hover:underline">
                      See all {quotes.total}
                    </Link>
                  )}
                </>
              ) : (
                <EmptyArt
                  art="receipt"
                  title="No quotes yet"
                  action={
                    can(me, "quotes.create") && (
                      <LinkButton href={`/companies/${company.id}/quotes/new`} variant="primary" icon={<Plus className="size-4" aria-hidden />}>
                        Make a quote
                      </LinkButton>
                    )
                  }
                >
                  A quote for this customer, priced for them, shows up here.
                </EmptyArt>
              )
            ) : company.activities.length ? (
              <ActivityList activities={company.activities} org={me.org} hide={["company"]} empty="" />
            ) : (
              <EmptyArt
                art="notes"
                title="Nothing logged yet"
                action={mayLog && <LogActivityButton kind="note" label="Log activity" variant="primary" {...logProps} />}
              >
                Calls, meetings, emails, notes and tasks about this customer show up here, newest first.
              </EmptyArt>
            )}
          </Sheet>
        </div>

        <div className="space-y-5">
          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle icon="particulars">Details</SectionTitle>
            <div className="mt-2">
              <DetailSections
                sections={ownForm.sections
                  .map((section, i, all) => ({
                    title: section.title,
                    items: [
                      // The system's code for it heads the first section.
                      ...(i === 0 ? ([["Customer code", company.code]] as [string, ReactNode][]) : []),
                      ...layoutItems(fmt, section.fields, company, shownDetails, ["name", "status", "notes"]),
                      // Team and when it was added go with who it's assigned to (or last).
                      ...(section.fields.some((f) => f.key === "ownerId") || (i === all.length - 1 && !all.some((x) => x.fields.some((f) => f.key === "ownerId")))
                        ? ([["Team", company.team?.name ?? null], ["Added", fmt.whenLabel(company.createdAt)]] as [string, ReactNode][])
                        : []),
                    ],
                  }))
                  .filter((section) => section.items.length > 0)}
              />
              {company.notes && <p className="mt-4 border-t border-rule pt-3 text-sm whitespace-pre-line text-ink-2">{company.notes}</p>}
            </div>
          </Sheet>

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
                <Empty compact icon="deals" title="No deals yet">Add one to forecast what this customer may buy.</Empty>
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
              <Empty compact icon="customers" title="No contacts yet">Add the people you deal with here.</Empty>
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
              <p className="pt-2 text-meta text-ink-3">{company.contactCount - company.contacts.length} more belong to other people.</p>
            )}
          </Sheet>

          <AssociationsPanel kind="company" id={company.id} />

          {owed && isDoctor && owed.balance && (
            <Sheet className="px-5 pt-4 pb-5">
              <SectionTitle icon="money">Owes</SectionTitle>
              <p className="mt-2 text-figure text-ink">{fmt.peso(owed.balance.owedCentavos)}</p>
              <p className="mt-1 text-meta text-ink-3">
                {fmt.peso(owed.balance.balanceCentavos)} as of {fmt.dateLabel(owed.balance.asOf)}
                {owed.balance.collectedSinceCentavos > 0 && <>, less {fmt.peso(owed.balance.collectedSinceCentavos)} collected since</>}
              </p>
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
