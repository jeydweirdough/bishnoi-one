import { QuoteForm } from "../components/quote-form";
import { NoAccess } from "../components/admin/words";
import { customFields } from "../components/extra/load";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import type { CompanyDetail, ContactDetail, Deal, PriceList, StockAnswer } from "@/src/platform/lib/types";
import type { QuoteFor } from "../actions/customers";

export const metadata = { title: "New quote" };

type Params = Promise<{ id: string }>;
type Search = Promise<Record<string, string | string[] | undefined>>;

/** A new quote, for a company or for a contact. The price list is the customer's:
 *  its team's own prices stand over the company price list. */
async function NewQuote({ to, dealId }: { to: QuoteFor; dealId?: string }) {
  const me = await getCompanyMe();
  if (!can(me, "quotes.create")) return <NoAccess what="quotes" />;
  const base = `/${to.kind}/${enc(to.id)}`;
  const [customer, priceList, fields] = await Promise.all([
    to.kind === "companies" ? load<CompanyDetail>(base) : load<ContactDetail>(base),
    load<PriceList>(`${base}/price-list`),
    customFields("quote"),
  ]);
  // Started from a deal: the quote is made for it, when the deal is still within reach.
  const deal = dealId && can(me, "deals.view") ? await load<Deal>(`/deals/${enc(dealId)}`).catch(() => null) : null;
  // How much Inventory has, as the quote is started (a product it doesn't have is left out).
  const codes = priceList.products.map((p) => p.code);
  const stock = codes.length ? await load<StockAnswer>(`/stock?codes=${encodeURIComponent(codes.join(","))}`) : null;
  const list = to.kind === "companies" ? { href: "/companies", label: "Customers" } : { href: "/contacts", label: "Contacts" };
  return (
    <>
      <PageHeader crumbs={[list, { href: `/${to.kind}/${to.id}`, label: customer.name }]} title={`New quote for ${customer.name}`}>
        {deal ? `For the deal ${deal.name}${deal.lines.length ? ", starting with its products and their promos" : ""}. ` : ""}
        {customer.team ? `Priced with ${customer.team.name}'s prices. ` : ""}Promos and extra discounts are per product line.
        {stock?.linked && (
          <span className={`mt-1 block ${stock.error ? "text-danger" : "text-ink-3"}`}>
            {stock.error ? `Stock can't be shown: ${stock.error}` : "Stock is from Inventory, as of when this page opened."}
          </span>
        )}
      </PageHeader>
      <Sheet className="max-w-[70rem] px-5 py-6 sm:px-8">
        <QuoteForm to={to} priceList={priceList} org={me.org} fields={fields} stock={stock} deal={deal ? { id: deal.id, name: deal.name, priceType: deal.priceType, lines: deal.lines } : null} />
      </Sheet>
    </>
  );
}

export async function NewCompanyQuote({ params, searchParams }: { params: Params; searchParams: Search }) {
  const { id } = await params;
  const deal = (await searchParams).deal;
  return <NewQuote to={{ kind: "companies", id }} dealId={typeof deal === "string" ? deal : undefined} />;
}

export async function NewContactQuote({ params }: { params: Params }) {
  const { id } = await params;
  return <NewQuote to={{ kind: "contacts", id }} />;
}
