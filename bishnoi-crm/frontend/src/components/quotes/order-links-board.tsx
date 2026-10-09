"use client";

import { useRouter } from "next/navigation";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import type { QuoteLink, QuoteLinks } from "../../actions/quote-links";
import { LinkList, OrderLinkButton } from "./order-link-button";

/** Customers → Order links: every link this person made, a new one for someone not a customer yet. */
export function OrderLinksBoard({ links, choices, slug, mayMake }: { links: QuoteLink[]; choices: Pick<QuoteLinks, "priceTypes" | "lifetimes">; slug: string; mayMake: boolean }) {
  const router = useRouter();
  const make = mayMake && <OrderLinkButton slug={slug} label="New order link" variant="primary" onMade={() => router.refresh()} />;
  return (
    <>
      {links.length > 0 && <div className="mb-4 flex justify-end">{make}</div>}
      {links.length === 0 ? (
        <Sheet>
          <Empty icon="quotes" title="No order links yet" actions={make}>
            Send a link to someone who needs medicines: they say who they are, pick what they need at your prices, and send. They become your customer, and their order your quote. For an existing customer, use Order link on their page.
          </Empty>
        </Sheet>
      ) : (
        <LinkList links={links} choices={choices} onChanged={() => router.refresh()} showCustomer />
      )}
    </>
  );
}
