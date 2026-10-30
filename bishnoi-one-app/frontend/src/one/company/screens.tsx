import Link from "next/link";
import type { ReactNode } from "react";
import type { ServiceInfo } from "@/src/modules/console/actions/services";
import { ServiceCard } from "@/src/modules/console/components/organizations/service-card";
import { ago, when } from "@/src/modules/console/lib/words";
import { accountSend } from "@/src/platform/lib/account";
import { ApiError } from "@/src/platform/lib/api";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { AdministratorsCard, LetterheadForm, ProfileForm, SignOutButton } from "./forms";
import { CatalogueBoard } from "./catalogue";
import type { ActivityEntry, Administrators, CatalogueEntry, CompanyProfile, OffDomainPerson, SecurityData } from "./types";

// The company console (feature plan step 5, 2026-10-28): what a company's own administrators keep
// about their company in the Admin Console. People, roles and the org chart have their own pages.

/** What /identity/company gives, or null for someone who isn't the company's administrator. */
async function read<T>(path: string): Promise<T | null> {
  try {
    return await accountSend<T>("GET", path);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) return null;
    throw error;
  }
}

function NotYours() {
  return (
    <Sheet>
      <Empty icon="company" title="For your company's administrators">
        Only your company&apos;s administrators keep its settings. Ask one of them if something needs to change.
      </Empty>
    </Sheet>
  );
}

function Page({ title, intro, children }: { title: string; intro: ReactNode; children: ReactNode }) {
  return (
    <>
      <PageHeader title={title}>{intro}</PageHeader>
      {children}
    </>
  );
}

export async function CompanyProfilePage() {
  const [data, admins] = await Promise.all([
    read<{ company: CompanyProfile; offDomain: OffDomainPerson[] }>("/identity/company"),
    read<Administrators>("/identity/company/administrators"),
  ]);
  if (!data) return <Page title="Company profile" intro={null}><NotYours /></Page>;
  const c = data.company;
  return (
    <Page title="Company profile" intro="Your company as every app shows it.">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Sheet className="px-5 py-4">
          <SectionTitle icon="company">Details</SectionTitle>
          <div className="mt-3">
            <ProfileForm company={c} />
          </div>
        </Sheet>
        {admins && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="roles">Administrators</SectionTitle>
            <p className="mt-1 mb-3 text-meta text-ink-3">They run the company in Bishnoi One: this console, people, roles and apps.</p>
            <AdministratorsCard data={admins} />
          </Sheet>
        )}
        {data.offDomain.length > 0 && (
          <Sheet className="px-5 py-4 lg:col-span-2">
            <SectionTitle icon="email">Emails to change</SectionTitle>
            <p className="mt-1 mb-3 text-meta text-ink-3">
              Not at @{c.emailDomain}: they can&apos;t sign in until you change their email on{" "}
              <Link href="/platform/roles/people" className="text-hema hover:underline">People</Link> (⋯ → Change details). Their password stays.
            </p>
            <ul className="divide-y divide-rule">
              {data.offDomain.map((p) => (
                <li key={p.id} className="flex flex-wrap items-center gap-x-3 py-2 text-sm">
                  <span className="font-medium text-ink">{p.fullName}</span>
                  <span className="text-ink-3">{p.email}</span>
                </li>
              ))}
            </ul>
          </Sheet>
        )}
        <Sheet className="px-5 py-4 lg:col-span-2">
          <SectionTitle icon="documents">Letterhead</SectionTitle>
          <p className="mt-1 mb-3 text-meta text-ink-3">On every printed document: purchase orders, receipts, delivery notes, invoices.</p>
          <LetterheadForm company={c} />
        </Sheet>
        <Sheet className="px-5 py-4">
          <SectionTitle icon="particulars">On Bishnoi One</SectionTitle>
          <Particulars
            items={[
              ["Company number", c.no ?? "—"],
              ["Short name", c.slug],
              ["Status", c.status === "active" ? "Active" : "Suspended"],
              ["Since", when(c.createdAt)],
            ]}
          />
          <p className="mt-3 text-meta text-ink-3">The short name is in every sign-in and can&apos;t change. Bishnoi One&apos;s operators can help with anything here.</p>
        </Sheet>
      </div>
    </Page>
  );
}

export async function CompanyAppsPage() {
  const data = await read<{ apps: CatalogueEntry[] }>("/identity/company/catalogue");
  if (!data) return <Page title="Apps" intro={null}><NotYours /></Page>;
  return (
    <Page title="Apps" intro="Turn on the apps your company uses and, inside each, the features it needs. What's off is hidden from menus, forms and reports for everyone. Who may open each app is on People.">
      <CatalogueBoard apps={data.apps} />
    </Page>
  );
}

export async function IntegrationsPage() {
  const [data, company] = await Promise.all([read<{ services: ServiceInfo[] }>("/identity/company/services"), read<{ company: CompanyProfile }>("/identity/company")]);
  if (!data || !company) return <Page title="Integrations" intro={null}><NotYours /></Page>;
  return (
    <Page title="Integrations" intro="The outside services your apps use: email sending, Zoho Books, lead channels. Secrets are kept encrypted and never shown again once saved.">
      <div className="max-w-3xl space-y-4">
        {data.services.map((s) => (
          <ServiceCard
            key={s.key}
            mine
            companyId={company.company.id}
            service={s}
            canChange
            checkedWhen={s.check ? ago(s.check.at) : null}
            updatedWhen={s.updatedAt ? ago(s.updatedAt) : null}
          />
        ))}
      </div>
    </Page>
  );
}

export async function SecurityPage() {
  const data = await read<SecurityData>("/identity/company/security");
  if (!data) return <Page title="Security" intro={null}><NotYours /></Page>;
  const figures: [string, number, string][] = [
    ["Open sign-ins", data.openSignIns, "Across your people, now"],
    ["Without a password", data.withoutPassword, "Can't sign in yet: set one on People"],
    ["Administrators", data.administrators, "Can change every setting"],
  ];
  return (
    <Page title="Security" intro="Who can sign in, when each person last did, and their open sign-ins. Passwords and switching people off are on People.">
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        {figures.map(([label, n, note]) => (
          <Sheet key={label} className="px-5 py-4">
            <p className="text-meta text-ink-3">{label}</p>
            <p className={`text-2xl font-semibold ${label === "Without a password" && n > 0 ? "text-promo-ink" : "text-ink"}`}>{n}</p>
            <p className="text-meta text-ink-3">{note}</p>
          </Sheet>
        ))}
      </div>
      <Sheet className="px-5 pt-4 pb-2">
        <SectionTitle icon="password">People</SectionTitle>
        <ul className="mt-2 divide-y divide-rule">
          {data.people.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3">
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-ink">
                  {p.fullName}
                  {p.isCompanyAdmin && <span className="ml-2 rounded-full bg-bench px-2 py-0.5 text-meta font-normal text-ink-3">Administrator</span>}
                  {p.status !== "active" && <span className="ml-2 rounded-full bg-bench px-2 py-0.5 text-meta font-normal text-ink-3">Suspended</span>}
                </span>
                <span className="block truncate text-meta text-ink-3">
                  {p.email} · {p.hasPassword ? `password set ${p.passwordChangedAt ? ago(p.passwordChangedAt) : ""}` : "no password yet"}
                </span>
              </span>
              <span className="text-meta text-ink-2">{p.lastActiveAt ? `Last active ${ago(p.lastActiveAt)}` : "Never signed in"}</span>
              <span className="text-meta text-ink-2">
                {p.openSignIns} open {p.openSignIns === 1 ? "sign-in" : "sign-ins"}
              </span>
              <SignOutButton id={p.id} name={p.fullName} count={p.openSignIns} />
            </li>
          ))}
        </ul>
      </Sheet>
    </Page>
  );
}

const ACTIONS: Record<string, string> = {
  "company.updated": "Changed the company profile",
  "service.updated": "Changed an integration",
  "service.checked": "Tested an integration",
  "access.person_added": "Added a person",
  "access.person_changed": "Changed a person",
  "access.person_suspended": "Switched a person off",
  "access.person_reactivated": "Switched a person on",
  "access.password_set": "Set a password",
  "access.granted": "Gave an app",
  "access.withdrawn": "Took an app away",
  "user.suspended": "Suspended a person",
  "identity.signed_in": "Signed in",
  "identity.signed_out": "Signed out",
  "identity.switched_company": "Switched company",
  "identity.opened_app": "Opened an app",
  "identity.password_changed": "Changed their password",
  "organisation.unit_added": "Added a unit",
  "organisation.unit_changed": "Changed a unit",
  "organisation.branch_added": "Added a branch",
  "organisation.branch_changed": "Changed a branch",
  "organisation.person_placed": "Placed a person on the chart",
  "security.signed_out_person": "Signed a person out",
};

function said(action: string): string {
  return ACTIONS[action] ?? action.replace(/[._]/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export async function ActivityPage({ q, category, before }: { q: string; category: string; before: string }) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (category) params.set("category", category);
  if (before) params.set("before", before);
  const data = await read<{ entries: ActivityEntry[]; more: boolean }>(`/identity/company/activity?${params}`);
  if (!data) return <Page title="Activity log" intro={null}><NotYours /></Page>;
  const link = (over: Record<string, string>) => `/platform/company/activity?${new URLSearchParams({ ...(q && { q }), ...(category && { category }), ...over })}`;
  const tabs: [string, string][] = [["", "Everything"], ["admin", "Changes"], ["security", "Sign-ins and security"]];
  return (
    <Page title="Activity log" intro="Who did what at your company, newest first. It names what changed, never the values.">
      <Sheet className="px-5 pt-4 pb-2">
        <form className="flex flex-wrap items-center gap-3" action="/platform/company/activity">
          {category && <input type="hidden" name="category" value={category} />}
          <input
            name="q"
            defaultValue={q}
            placeholder="Find a person or a change"
            className="h-9 w-full max-w-xs rounded-lg border border-rule-strong bg-sheet px-3 text-sm"
            aria-label="Find a person or a change"
          />
          <nav className="flex gap-1" aria-label="Kind of activity">
            {tabs.map(([key, label]) => (
              <Link
                key={key}
                href={link({ category: key })}
                aria-current={category === key ? "page" : undefined}
                className={`rounded-md px-3 py-1 text-meta ${category === key ? "bg-hema-tint font-semibold text-ink" : "text-ink-3 hover:bg-bench"}`}
              >
                {label}
              </Link>
            ))}
          </nav>
        </form>
        {data.entries.length === 0 ? (
          <Empty icon="auditLog" title="Nothing here yet">
            Changes and sign-ins at your company are listed as they happen.
          </Empty>
        ) : (
          <ul className="mt-3 divide-y divide-rule">
            {data.entries.map((e) => (
              <li key={e.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-2.5 text-sm">
                <time dateTime={e.at} title={when(e.at)} className="w-24 shrink-0 text-meta text-ink-3">
                  {ago(e.at)}
                </time>
                <span className="min-w-0 flex-1">
                  <span className="font-medium text-ink">{e.actor}</span> <span className="text-ink-2">{said(e.action).toLowerCase()}</span>
                  {e.target && <span className="text-ink-2">: {e.target}</span>}
                  {e.fields.length > 0 && <span className="text-meta text-ink-3"> ({e.fields.join(", ")})</span>}
                </span>
              </li>
            ))}
          </ul>
        )}
        {data.more && (
          <div className="py-3">
            <Link href={link({ before: data.entries[data.entries.length - 1].at })} className="text-sm font-medium text-sage-deep hover:underline">
              Older
            </Link>
          </div>
        )}
      </Sheet>
    </Page>
  );
}
