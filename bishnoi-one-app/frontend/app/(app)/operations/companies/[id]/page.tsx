// One company: its particulars, the applications it has, its departments and
// branches, its people, what's open with Support, and what was done to it.
import type { Metadata } from "next";
import Link from "next/link";
import { Figure } from "@/src/modules/console/platform/ui/figure";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/modules/console/platform/ui/sheet";
import { enc, load } from "@/src/modules/console/platform/lib/api";
import { ActivityList } from "@/src/modules/console/components/activity-list";
import { getStaff } from "@/src/modules/console/components/gate";
import { Count, IncidentSeverityMark, IncidentStatusMark, KindMark, SeverityMark, Tabs, TicketStatusMark } from "@/src/modules/console/components/marks";
import { CompanyApps } from "@/src/modules/console/components/organizations/company-apps";
import { ServiceCard } from "@/src/modules/console/components/organizations/service-card";
import type { ServiceInfo } from "@/src/modules/console/actions/services";
import { DeleteRecord } from "@/src/modules/console/components/delete-record";
import { SuspendCompany } from "@/src/modules/console/components/organizations/company-tools";
import { EditLink, SuspendedTag } from "@/src/modules/console/components/organizations/record-tools";
import { Structure } from "@/src/modules/console/components/organizations/structure";
import type { AuditEntry, CompanyDetail, Options, PlatformUser, Ticket } from "@/src/modules/console/lib/types";
import { ago, plural, when } from "@/src/modules/console/lib/words";

type Props = { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

const TABS = ["overview", "applications", "connections", "structure", "users", "issues", "activity"] as const;
type Tab = (typeof TABS)[number];

const getCompany = (id: string) => load<{ company: CompanyDetail }>(`/platform/companies/${enc(id)}`).then((b) => b.company);

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  return { title: (await getCompany(id)).name };
}

export default async function CompanyPage({ params, searchParams }: Props) {
  const [{ id }, search] = await Promise.all([params, searchParams]);
  const tab: Tab = TABS.includes(search.tab as Tab) ? (search.tab as Tab) : "overview";
  const [company, staff] = await Promise.all([getCompany(id), getStaff()]);
  const suspended = company.status === "suspended";
  const href = (t: Tab) => `/operations/companies/${company.id}${t === "overview" ? "" : `?tab=${t}`}`;

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/operations/companies", label: "Companies" }]}
        title={company.name}
        tools={
          <>
            {suspended && <SuspendedTag />}
            {staff.canAdminister && (
              <>
                <EditLink href={`/operations/companies/${company.id}/edit`} what={company.name} />
                <SuspendCompany id={company.id} name={company.name} status={company.status} people={company.userCount} />
                <DeleteRecord
                  kind="company"
                  id={company.id}
                  name={company.name}
                  after="/operations/companies"
                  done="Company deleted"
                  body={`${company.name} is removed from the platform with its ${company.userCount === 1 ? "1 person" : `${company.userCount} people`}, their access, its structure and connections. Tickets it raised stay. Its data inside each application (the CRM's customers, Inventory's stock) isn't touched. It can't be undone; to keep it, suspend it instead.`}
                />
              </>
            )}
          </>
        }
      >
        {suspended ? (
          <span className="font-semibold text-danger">
            Suspended {company.suspendedAt ? ago(company.suspendedAt) : ""}. Its {plural(company.userCount, "person", "people")} can&apos;t work in any application.
          </span>
        ) : (
          <>
            {company.no && <span className="tabular-nums">No. {company.no} · </span>}
            {company.slug} · {plural(company.userCount, "user")} · {plural(company.appCount, "application")}
          </>
        )}
      </PageHeader>

      <Tabs
        current={tab}
        tabs={[
          { key: "overview", label: "Overview", href: href("overview") },
          { key: "applications", label: "Applications", href: href("applications"), count: company.applications.length },
          { key: "connections", label: "Connections", href: href("connections") },
          { key: "structure", label: "Structure", href: href("structure"), count: company.units.length },
          { key: "users", label: "People", href: href("users"), count: company.userCount },
          { key: "issues", label: "Issues", href: href("issues"), count: company.openTickets + company.activeIncidents.length },
          { key: "activity", label: "Activity", href: href("activity") },
        ]}
      />

      {tab === "overview" && <Overview company={company} />}
      {tab === "applications" && <Applications company={company} canChange={staff.canAdminister} />}
      {tab === "connections" && <Connections company={company} canChange={staff.canAdminister} />}
      {tab === "structure" && <Structure companyId={company.id} companyName={company.name} units={company.units} canChange={staff.canAdminister} />}
      {tab === "users" && <People company={company} />}
      {tab === "issues" && <Issues company={company} />}
      {tab === "activity" && <Activity company={company} />}
    </>
  );
}

/** The outside services this company's applications use: filled in here, given to each application that uses them. */
async function Connections({ company, canChange }: { company: CompanyDetail; canChange: boolean }) {
  const { services } = await load<{ services: ServiceInfo[] }>(`/platform/companies/${enc(company.id)}/services`);
  return (
    <div className="max-w-3xl space-y-4">
      <p className="text-meta text-ink-3">
        The details {company.name}&apos;s applications need to reach outside services. Secrets are kept encrypted and never shown again once saved; only the
        applications that use a service are given it, so nothing is kept on their servers.
      </p>
      {services.map((s) => (
        <ServiceCard
          key={s.key}
          companyId={company.id}
          service={s}
          canChange={canChange}
          checkedWhen={s.check ? ago(s.check.at) : null}
          updatedWhen={s.updatedAt ? ago(s.updatedAt) : null}
        />
      ))}
      {!canChange && <p className="text-meta text-ink-3">A Platform Admin changes these.</p>}
    </div>
  );
}

function Overview({ company }: { company: CompanyDetail }) {
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
      <div className="space-y-5">
        <Sheet className="grid grid-cols-2 divide-rule sm:grid-cols-4 sm:divide-x">
          <Figure label="People" value={company.userCount} href={`/operations/companies/${company.id}?tab=users`} />
          <Figure label="Active users" value={company.status === "suspended" ? 0 : company.activeUserCount} />
          <Figure label="Applications" value={company.appCount} href={`/operations/companies/${company.id}?tab=applications`} />
          <Figure label="Open tickets" value={company.openTickets} href={`/operations/companies/${company.id}?tab=issues`} />
        </Sheet>
        <Sheet className="px-5 py-4">
          <SectionTitle icon="particulars">Details</SectionTitle>
          <div className="mt-3">
            <Particulars
              items={[
                ["Company code", company.slug],
                ["Status", company.status === "suspended" ? `Suspended since ${when(company.suspendedAt)}` : "Active"],
                ["Currency", company.currency],
                ["Time zone", company.timezone],
                ["Email domain", company.emailDomain ? `@${company.emailDomain}` : "Not set"],
                ["Contact email", company.contactEmail ? <a href={`mailto:${company.contactEmail}`} className="text-hema hover:underline">{company.contactEmail}</a> : null],
                ["Departments", company.units.filter((u) => u.kind === "department").length],
                ["Branches", company.units.filter((u) => u.kind === "branch").length],
                ["Created on", when(company.createdAt)],
                ["Notes", company.notes ? <span className="whitespace-pre-line">{company.notes}</span> : null],
              ]}
            />
          </div>
        </Sheet>
      </div>
      <div className="space-y-5">
        <Sheet>
          <div className="px-5 pt-4 pb-2">
            <SectionTitle icon="roles">
              Company admins
              <Count n={company.admins.length} />
            </SectionTitle>
          </div>
          {company.admins.length === 0 ? (
            <Empty title="No company admins yet" icon="person">
              Make one of its users a company admin from their page (Edit, then “Company admin”).
            </Empty>
          ) : (
            <ul className="divide-y divide-rule border-t border-rule" role="list">
              {company.admins.map((a) => (
                <li key={a.id} className="px-5 py-2.5">
                  <Link href="/operations/people" className="block truncate font-semibold text-hema hover:underline">
                    {a.name}
                  </Link>
                  <span className="block truncate text-meta text-ink-3">{a.email}</span>
                </li>
              ))}
            </ul>
          )}
        </Sheet>
        <IncidentsSheet company={company} />
      </div>
    </div>
  );
}

function IncidentsSheet({ company }: { company: CompanyDetail }) {
  return (
    <Sheet>
      <div className="px-5 pt-4 pb-2">
        <SectionTitle icon="incidents">
          Active incidents affecting it
          <Count n={company.activeIncidents.length} />
        </SectionTitle>
      </div>
      {company.activeIncidents.length === 0 ? (
        <Empty title="No active incidents" icon="incidents">
          An incident affects {company.name} when it names the company, or names no company and is on an application it uses.
        </Empty>
      ) : (
        <ul className="divide-y divide-rule border-t border-rule" role="list">
          {company.activeIncidents.map((i) => (
            <li key={i.id}>
              <div className="block px-5 py-2.5 hover:bg-bench/40">
                <span className="block truncate text-sm font-semibold text-ink">
                  {i.number} {i.title}
                </span>
                <span className="mt-0.5 flex flex-wrap items-center gap-2">
                  <IncidentSeverityMark severity={i.severity} />
                  <IncidentStatusMark status={i.status} />
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}

async function Applications({ company, canChange }: { company: CompanyDetail; canChange: boolean }) {
  const options = canChange ? await load<Options>("/platform/options") : null;
  return (
    <Sheet className="max-w-3xl">
      <div className="px-5 pt-4 pb-2">
        <SectionTitle icon="apps">Assigned applications</SectionTitle>
        <p className="text-meta text-ink-3">
          {canChange ? "Select the applications this company subscribes to. Its users can only be given access to these." : "Its users can only be given access to these. A Platform Admin changes them."}
        </p>
      </div>
      <div className="border-t border-rule">
        {!canChange && company.applications.length === 0 ? (
          <Empty title="No applications yet" icon="apps">
            A Platform Admin assigns applications here.
          </Empty>
        ) : (
          <CompanyApps company={company} applications={options?.applications ?? []} canChange={canChange} />
        )}
      </div>
    </Sheet>
  );
}

/**
 * Its people, to look at (decided 2026-10-29: Companies → Users retired). Its administrators add and
 * change them on People; an operator switches to the company (the sidebar's company switcher) to do it.
 */
async function People({ company }: { company: CompanyDetail }) {
  const { users } = await load<{ users: PlatformUser[] }>(`/platform/users?company_id=${enc(company.id)}`);
  const domain = company.emailDomain;
  return (
    <Sheet>
      <div className="px-5 pt-4 pb-2">
        <SectionTitle icon="people">
          People at {company.name}
          <Count n={users.length} />
        </SectionTitle>
        <p className="mt-1 text-meta text-ink-3">
          {company.name}&apos;s administrators add and change its people on People. To do it yourself, switch to {company.name} from the sidebar&apos;s company switcher.
        </p>
      </div>
      <div className="border-t border-rule">
        {users.length === 0 ? (
          <Empty title="No people yet" icon="people" source={`${company.name}'s administrators, on People.`} />
        ) : (
          <ul className="divide-y divide-rule">
            {users.map((u) => {
              const off = Boolean(domain) && !u.email.toLowerCase().endsWith(`@${domain}`) && u.status === "active";
              return (
                <li key={u.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-2.5">
                  <span className="min-w-0 flex-1">
                    <span className={`block truncate text-sm font-medium ${u.status === "active" ? "text-ink" : "text-ink-3 line-through"}`}>{u.fullName}</span>
                    <span className="block truncate text-meta text-ink-3">{u.email}</span>
                  </span>
                  <span className="flex flex-wrap gap-1.5 text-meta">
                    {u.isCompanyAdmin && <span className="rounded-full bg-hema-tint px-2 py-0.5 text-hema">Administrator</span>}
                    {u.status !== "active" && <span className="rounded-full border border-rule px-2 py-0.5 text-ink-3">Suspended</span>}
                    {off && <span className="rounded-full bg-danger-tint px-2 py-0.5 text-danger" title={`Not at @${domain}: can't sign in until it's changed`}>Email to change</span>}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Sheet>
  );
}

async function Issues({ company }: { company: CompanyDetail }) {
  const { tickets } = await load<{ tickets: Ticket[] }>(`/platform/tickets?company_id=${enc(company.id)}&state=open`);
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
      <Sheet className="self-start">
        <div className="px-5 pt-4 pb-2">
          <SectionTitle icon="support">
            Open tickets
            <Count n={tickets.length} />
          </SectionTitle>
        </div>
        {tickets.length === 0 ? (
          <Empty title="No open tickets" icon="support">
            When {company.name} reports a complaint, a bug or a question, it shows here until it&apos;s closed.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule border-t border-rule" role="list">
            {tickets.map((t) => (
              <li key={t.id}>
                <div className="block px-5 py-3 hover:bg-bench/40">
                  <span className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-meta text-ink-3">{t.number}</span>
                    <span className="min-w-0 font-semibold text-ink">{t.title}</span>
                  </span>
                  <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                    <SeverityMark severity={t.severity} />
                    <TicketStatusMark status={t.status} />
                    <KindMark kind={t.kind} />
                    {t.application && <span className="text-meta text-ink-3">{t.application.name}</span>}
                    <span className="text-meta text-ink-3">{ago(t.createdAt)}</span>
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
      <IncidentsSheet company={company} />
    </div>
  );
}

async function Activity({ company }: { company: CompanyDetail }) {
  const { entries } = await load<{ entries: AuditEntry[] }>(`/platform/activity?company_id=${enc(company.id)}`);
  return (
    <Sheet className="px-5 py-4">
      <SectionTitle icon="auditLog">Activity</SectionTitle>
      <div className="mt-2">
        <ActivityList entries={entries} empty={`No activity for ${company.name} yet.`} />
      </div>
    </Sheet>
  );
}
