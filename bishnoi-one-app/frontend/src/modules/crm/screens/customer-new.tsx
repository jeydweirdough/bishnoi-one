import { CustomerForm } from "@/src/modules/crm/components/customer-form";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { crmWorkspace, teamsFor } from "@/src/platform/lib/module";
import { orgLists, pickableTeams } from "@/src/platform/lib/org";

export const metadata = { title: "Add customer" };

export default async function NewCustomerPage() {
  const ws = await crmWorkspace();
  // Every team they may add to, in any division they sell in. The form asks
  // which division only when there is more than one to ask about.
  const [teams, lists] = await Promise.all([pickableTeams(teamsFor(ws, "create")), orgLists()]);

  return (
    <>
      <PageHeader crumbs={[{ href: "/crm/customers", label: "Customers" }]} title="Add customer" />
      <Sheet className="max-w-[55rem] px-5 py-6 sm:px-8">
        {teams.length === 0 ? (
          <p className="text-ink-2">You can see customers but can&apos;t add them. Ask your admin if you need to.</p>
        ) : (
          <CustomerForm teams={teams} kinds={lists.customer_kind} />
        )}
      </Sheet>
    </>
  );
}
