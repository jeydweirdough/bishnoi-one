import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { LeadFinder } from "@/src/modules/crm/components/leads/lead-finder";

export const metadata = { title: "Find leads with AI" };

/** Find leads with AI: the person's own chatbot searches the web; what it finds is checked here and added as their customers. */
export default async function LeadFinderPage() {
  const me = await getCompanyMe();
  if (!can(me, "customers.create")) return <NoAccess what="adding customers" />;
  const finder = await load<{ team: string | null; types: { code: string; name: string }[] }>("/leads/finder");
  return (
    <>
      <PageHeader title="Find leads with AI" crumbs={[{ href: "/crm/companies", label: "Customers" }]}>
        Your AI (ChatGPT, Claude or DeepSeek) searches the internet; you check what it found and add the good ones to your customers.
      </PageHeader>
      <LeadFinder company={me.org.name} team={finder.team} types={finder.types} defaultWhere="" />
    </>
  );
}
