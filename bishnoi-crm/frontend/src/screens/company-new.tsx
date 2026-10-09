import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { Assignable, CustomerType } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { CompanyForm } from "../components/crm/company-form";
import { CustomerStart } from "../components/crm/new-customer";
import { formLayout } from "../components/extra/load";
import { priceGroupsFor } from "../components/catalogue/price-groups";

export const metadata = { title: "Add a customer" };

type Search = Promise<Record<string, string | string[] | undefined>>;

export default async function NewCompanyPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "customers.create")) return <NoAccess what="adding customers" />;
  const params = await searchParams;
  const name = typeof params.name === "string" ? params.name.slice(0, 200) : "";
  const then = params.then === "quote" || params.then === "deal" ? params.then : null;
  const next = then && `Once they're saved, their new ${then} opens.`;
  const kind = typeof params.type === "string" ? params.type : "";
  const team = typeof params.team === "string" ? params.team : undefined;
  const [people, types, layout, priceGroups] = await Promise.all([
    load<Assignable[]>("/people/assignable"),
    load<CustomerType[]>("/customer-types"),
    formLayout("company"),
    priceGroupsFor(me),
  ]);
  // The first questions come first (from a link, or a bookmark): then the form made for the answers.
  if (!kind) {
    return (
      <>
        <PageHeader title="Add a customer" crumbs={[{ href: "/companies", label: "Customers" }]}>
          {next}
        </PageHeader>
        <Sheet className="max-w-xl px-5 pt-5 pb-6">
          <CustomerStart choices={{ people, types }} initialName={name} then={then} />
        </Sheet>
      </>
    );
  }
  return (
    <>
      <PageHeader title="Add a customer" crumbs={[{ href: "/companies", label: "Customers" }]}>
        {next}
      </PageHeader>
      <Sheet className="px-5 pt-5 pb-6">
        <CompanyForm
          people={people}
          types={types}
          layout={layout}
          priceGroups={priceGroups}
          initialName={name}
          initialTeam={team}
          initialType={kind}
          then={then}
        />
      </Sheet>
    </>
  );
}
