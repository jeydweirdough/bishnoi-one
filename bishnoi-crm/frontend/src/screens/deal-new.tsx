import { Button } from "@/src/platform/ui/button";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import type { Assignable, CompanyDetail, CompanyRow, Deal, DealLists, DealStage, Paged, PriceList } from "@/src/platform/lib/types";
import { NoAccess } from "../components/admin/words";
import { DealForm } from "../components/deals/deal-form";

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
    const companies = await load<Paged<CompanyRow>>("/companies?limit=200");
    return (
      <>
        <PageHeader crumbs={[{ href: "/deals", label: "Deals" }]} title="New deal">
          A deal is with a customer. Pick which one.
        </PageHeader>
        <Sheet className="max-w-xl px-5 py-6 sm:px-8">
          {companies.items.length === 0 ? (
            <p className="text-sm text-ink-2">There are no customers you can see yet. Add one first, then its deal.</p>
          ) : (
            <form method="get" className="flex flex-wrap items-end gap-3">
              <label className="min-w-0 flex-1">
                <span className="mb-1 block text-meta font-medium text-ink-2">Customer</span>
                <select
                  name="company"
                  required
                  className="block h-9 w-full border-0 border-b border-control bg-transparent text-sm focus:border-hema focus:outline-none"
                >
                  {companies.items.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <Button type="submit" variant="primary">
                Continue
              </Button>
            </form>
          )}
        </Sheet>
      </>
    );
  }

  const [company, stages, lists, people, priceList] = await formData(companyId, can(me, "quotes.view"));
  return (
    <>
      <PageHeader crumbs={[{ href: "/deals", label: "Deals" }, { href: `/companies/${company.id}`, label: company.name }]} title={`New deal with ${company.name}`}>
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
      <PageHeader crumbs={[{ href: "/deals", label: "Deals" }, { href: `/deals/${deal.id}`, label: deal.name }]} title={`Edit ${deal.name}`}>
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
