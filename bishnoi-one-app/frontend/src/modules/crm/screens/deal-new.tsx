import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import type { Assignable, CompanyDetail, Deal, DealLists, DealStage, PriceList } from "@/src/platform/lib/types";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { DealForm } from "@/src/modules/crm/components/deals/deal-form";
import { CustomerStep } from "@/src/modules/crm/components/deals/new-deal";

export const metadata = { title: "New deal" };

type Search = Promise<Record<string, string | string[] | undefined>>;

/** What the deal form needs for a customer: its contacts, the stages and lists, who can own it, and its prices. */
async function formData(companyId: string, mayPrice: boolean) {
  return Promise.all([
    load<CompanyDetail>(`/companies/${enc(companyId)}`),
    load<DealStage[]>("/deal-stages"),
    load<DealLists>("/deal-lists"),
    load<Assignable[]>("/people/assignable"),
    mayPrice ? load<PriceList>(`/companies/${enc(companyId)}/price-list`).catch(() => null) : Promise.resolve(null),
  ]);
}

/** A new deal is always on a customer: picked first when it wasn't started from one. */
export default async function NewDealPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!can(me, "deals.create")) return <NoAccess what="adding deals" />;
  const asked = (await searchParams).company;
  const companyId = typeof asked === "string" ? asked : "";

  if (!companyId) {
    return (
      <>
        <PageHeader crumbs={[{ href: "/crm/deals", label: "Deals" }]} title="New deal">
          A deal is with a customer. Which one?
        </PageHeader>
        <Sheet className="max-w-xl px-5 py-6 sm:px-8">
          <CustomerStep />
        </Sheet>
      </>
    );
  }

  const [company, stages, lists, people, priceList] = await formData(companyId, can(me, "quotes.view"));
  return (
    <>
      <PageHeader crumbs={[{ href: "/crm/deals", label: "Deals" }, { href: `/crm/customers/${company.id}`, label: company.name }]} title={`New deal with ${company.name}`}>
        It starts in the first stage unless you pick another.
      </PageHeader>
      <Sheet className="max-w-[56rem] px-5 py-6 sm:px-8">
        <DealForm
          org={me.org}
          company={{ id: company.id, name: company.name, leadSource: company.leadSource }}
          contacts={company.contacts.map((c) => ({ id: c.id, name: c.name }))}
          stages={stages}
          lists={lists}
          people={people}
          priceList={priceList}
        />
      </Sheet>
    </>
  );
}

export async function EditDealPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await getCompanyMe();
  if (!can(me, "deals.edit")) return <NoAccess what="changing deals" />;
  const { id } = await params;
  const deal = await load<Deal>(`/deals/${enc(id)}`);
  if (!deal.can.edit) return <NoAccess what="changing this deal" />;
  const [company, stages, lists, people, priceList] = await formData(deal.company.id, can(me, "quotes.view"));
  return (
    <>
      <PageHeader crumbs={[{ href: "/crm/deals", label: "Deals" }, { href: `/crm/deals/${deal.id}`, label: deal.name }]} title={`Edit ${deal.name}`}>
        {deal.state === "open" ? "Moving it to another stage brings that stage's probability and forecast, unless you change them here too." : "It's closed: reopen it to change its stage or forecast."}
      </PageHeader>
      <Sheet className="max-w-[56rem] px-5 py-6 sm:px-8">
        <DealForm
          org={me.org}
          company={{ id: company.id, name: company.name }}
          contacts={company.contacts.map((c) => ({ id: c.id, name: c.name }))}
          stages={stages}
          lists={lists}
          people={people}
          priceList={priceList}
          deal={deal}
        />
      </Sheet>
    </>
  );
}
