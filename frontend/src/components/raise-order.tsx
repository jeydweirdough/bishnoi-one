import { ArrowUpRight } from "lucide-react";
import { buttonClass } from "@/src/platform/ui/button";
import type { Quote } from "@/src/platform/lib/types";

/** Take an agreed quote into the Orders app.
 *
 *  A quote is a price the customer has already accepted, so an order raised
 *  from one should not be typed out again: the Orders app fetches it from Orbit
 *  (`/orders-api/v1/quotes/{id}`) and fills its form in. It opens in its own tab
 *  because the person is already signed in there — the two apps share a
 *  sign-in — and because the quote is worth keeping open beside it.
 *
 *  This is a link and nothing more. Whether a quote became an order, and what
 *  happened to that order afterwards, is the Orders app's to answer: it keeps
 *  the quote's id on the order. Orbit holding its own copy would be the same
 *  fact written in two places, wrong the moment they disagree.
 *
 *  Nothing is shown when the Orders app hasn't been set up (`ordersUrl` unset),
 *  when the person doesn't raise orders in the quote's own division and team,
 *  or while Finance hasn't finished with it. The API refuses all three again. */
export function RaiseOrder({ quote, ordersUrl }: { quote: Quote; ordersUrl: string | null | undefined }) {
  if (!ordersUrl || !quote.can.order) return null;
  return (
    <a
      // The Orders app's own new-order page. `?quote=` is what it reads to
      // fetch the quote from Orbit and fill itself in.
      href={`${ordersUrl.replace(/\/$/, "")}/new-order?quote=${encodeURIComponent(quote.id)}`}
      target="_blank"
      rel="noopener"
      className={buttonClass("primary")}
    >
      <ArrowUpRight className="size-4" aria-hidden />
      Raise an order
      <span className="sr-only">(opens the Orders app in a new tab)</span>
    </a>
  );
}
