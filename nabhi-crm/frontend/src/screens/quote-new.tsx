import { QuoteForm } from "../components/quote-form";
import { NoAccess } from "../components/admin/words";
import { customFields } from "../components/extra/load";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import type { CompanyDetail, ContactDetail, PriceList } from "@/src/platform/lib/types";
import type { QuoteFor } from "../actions/customers";

export const metadata = { title: "New quote" };

type Params = Promise<{ id: string }>;

/** A new quote, for a company or for a contact. The price list is the customer's:
 *  its team's own prices stand over the company price list. */
async function NewQuote({ to }: { to: QuoteFor }) {
  const me = await getCompanyMe();
  if (!can(me, "quotes.create")) return <NoAccess what="quotes" />;
  const base = `/${to.kind}/${enc(to.id)}`;
  const [customer, priceList, fields] = await Promise.all([
    to.kind === "companies" ? load<CompanyDetail>(base) : load<ContactDetail>(base),
    load<PriceList>(`${base}/price-list`),
    customFields("quote"),
  ]);
  const list = to.kind === "companies" ? { href: "/companies", label: "Customers" } : { href: "/contacts", label: "Contacts" };
  return (
    <>
      <PageHeader crumbs={[list, { href: `/${to.kind}/${to.id}`, label: customer.name }]} title={`New quote for ${customer.name}`}>
        {customer.team ? `Priced with ${customer.team.name}'s prices. ` : ""}Promos and extra discounts are per product line.
      </PageHeader>
      <Sheet className="max-w-[70rem] px-5 py-6 sm:px-8">
        <QuoteForm to={to} priceList={priceList} org={me.org} fields={fields} />
      </Sheet>
    </>
  );
}

export async function NewCompanyQuote({ params }: { params: Params }) {
  const { id } = await params;
  return <NewQuote to={{ kind: "companies", id }} />;
}

export async function NewContactQuote({ params }: { params: Params }) {
  const { id } = await params;
  return <NewQuote to={{ kind: "contacts", id }} />;
}
