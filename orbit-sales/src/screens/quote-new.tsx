import { QuoteForm } from "../components/quote-form";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import type { CustomerDetail, PriceList } from "@/src/platform/lib/types";

export const metadata = { title: "New quote" };

export default async function NewQuotePage({ params }: { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { id } = await params;
  // The price list belongs to the customer: its division decides which prices
  // may be quoted, and its team's own prices stand over the company's.
  const [me, customer, priceList] = await Promise.all([
    getCompanyMe(),
    load<CustomerDetail>(`/sales/customers/${enc(id)}`),
    load<PriceList>(`/sales/customers/${enc(id)}/price-list`),
  ]);
  return (
    <>
      <PageHeader
        crumbs={[
          { href: "/customers", label: "Customers" },
          { href: `/customers/${id}`, label: customer.name },
        ]}
        title={`New quote for ${customer.name}`}
      >
        Only {customer.divisionName}&apos;s prices are offered. Promos and extra discounts are per product line.
      </PageHeader>
      <Sheet className="max-w-[70rem] px-5 py-6 sm:px-8">
        {customer.can.log ? (
          <QuoteForm customerId={id} priceList={priceList} org={me.org} />
        ) : (
          <p className="text-ink-2">You can see this customer but can&apos;t make quotes for them.</p>
        )}
      </Sheet>
    </>
  );
}
