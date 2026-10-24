import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { QuoteLinks } from "@/src/modules/crm/actions/quote-links";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { OrderLinksBoard } from "@/src/modules/crm/components/quotes/order-links-board";

export const metadata = { title: "Order links" };

/** The order links this person made: for customers, and for people who become one when they order. */
export default async function OrderLinksPage() {
  const me = await getCompanyMe();
  if (!can(me, "quotes.view")) return <NoAccess what="order links" />;
  const data = await load<QuoteLinks>("/quote-links");
  return (
    <>
      <PageHeader title="Order links">
        Links you send so someone can order their medicines at your prices, once, before the link expires. A person not yet a customer becomes yours when they order.
      </PageHeader>
      <OrderLinksBoard links={data.items} choices={data} slug={me.org.slug} mayMake={can(me, "quotes.create") && can(me, "customers.create")} />
    </>
  );
}
