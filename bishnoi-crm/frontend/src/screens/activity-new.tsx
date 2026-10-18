import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, query } from "@/src/platform/lib/api";
import type { Assignable, CrmKind, Ref } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { LogActivityPageForm } from "../components/crm/log-activity-page";
import { KINDS } from "../components/crm/words";

export const metadata = { title: "Log activity" };

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

/**
 * Logging a call, meeting, email, note or task, on a page of its own. Opened
 * from anywhere with what's known already: the kind (?kind=), the customer
 * (?company=) or contact (?contact=), and where to go back to (?back=).
 */
export default async function NewActivityPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "activities.create")) return <NoAccess what="logging activities" />;
  const s = await searchParams;
  const kind = (KINDS.some((k) => k.kind === one(s.kind)) ? one(s.kind) : "call") as CrmKind;
  const companyId = one(s.company);
  const contactId = one(s.contact);
  // Only a path inside the CRM, so the page can't send anyone elsewhere.
  const back = one(s.back).startsWith("/") && !one(s.back).startsWith("//") ? one(s.back) : "/activities";
  // One request: who it can be for, and the customer's contacts (or, without a customer, the customers to pick from).
  const { data } = await query<{ people: Assignable[] | null; company?: { id: string; name: string; contacts: Ref[] } | null; companies?: { items: Ref[] } | null }>(
    `query NewActivity($company: String!, $withCompany: Boolean!, $pick: Boolean!) {
      people { id name isMe team { id name } }
      company(id: $company) @include(if: $withCompany) { id name contacts { id name } }
      companies(limit: 200) @include(if: $pick) { items { id name } }
    }`,
    { company: companyId || "", withCompany: Boolean(companyId), pick: !companyId && can(me, "customers.view") },
  );
  const company = data.company ?? null;
  return (
    <>
      <PageHeader
        title="Log activity"
        crumbs={company ? [{ href: `/companies/${company.id}`, label: company.name }] : [{ href: "/activities", label: "Activities" }]}
      >
        {company ? `With ${company.name}: it's kept on their page, with the rest of their history.` : "A call, meeting, email, note or task: it's kept on the customer's page."}
      </PageHeader>
      <Sheet className="max-w-3xl px-5 py-6 sm:px-8">
        <LogActivityPageForm
          back={back}
          org={me.org}
          now={new Date().toISOString()}
          people={data.people ?? []}
          companyId={company?.id}
          contactId={contactId || undefined}
          contacts={company?.contacts ?? []}
          companies={company ? undefined : (data.companies?.items ?? []).map((c) => ({ id: c.id, name: c.name }))}
          initialKind={kind}
        />
      </Sheet>
    </>
  );
}
