import { notFound } from "next/navigation";
import { CustomerForm } from "../components/customer-form";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { crmWorkspace, teamsFor } from "@/src/platform/lib/module";
import { orgLists, pickableTeams } from "@/src/platform/lib/org";
import type { CustomerDetail } from "@/src/platform/lib/types";

export const metadata = { title: "Edit customer" };

export default async function EditCustomerPage({ params }: { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { id } = await params;
  const ws = await crmWorkspace();
  const customer = await load<CustomerDetail>(`/crm/customers/${enc(id)}`);
  if (!customer.can.edit) notFound();
  // Moving needs edit rights in the new team too, so only those are offered —
  // plus its own, which stays offered even if it has since been switched off.
  const [teams, lists] = await Promise.all([
    pickableTeams(teamsFor(ws, "edit"), { division: customer.division, team: customer.team }),
    orgLists(),
  ]);

  return (
    <>
      <PageHeader
        crumbs={[
          { href: "/customers", label: "Customers" },
          { href: `/customers/${id}`, label: customer.name },
        ]}
        title={`Edit ${customer.name}`}
      />
      <Sheet className="max-w-[55rem] px-5 py-6 sm:px-8">
        <CustomerForm teams={teams} kinds={lists.customer_kind} customer={customer} />
      </Sheet>
    </>
  );
}
