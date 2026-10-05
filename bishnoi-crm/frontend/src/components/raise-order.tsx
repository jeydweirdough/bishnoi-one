"use client";

import { ArrowUpRight, PackageCheck, Send } from "lucide-react";
import { toast } from "sonner";
import { raiseOrder } from "@/src/actions/quote-order";
import { buttonClass } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import type { Quote } from "@/src/platform/lib/types";

/** Raise an order in Bishnoi One Order from this quote.
 *
 *  The CRM sends the quote to Bishnoi One Order's API (backend app/orders.py has the
 *  payload) and keeps the order number it answers with, so a quote is ordered
 *  once. After that this shows the order instead of the button.
 *
 *  Shown to people who raise orders. Until Bishnoi One Order is connected, and until
 *  the quote is approved and its letter checked, the button is there but off,
 *  and says why on hover. */
export function RaiseOrder({
  quote,
  linked,
  mayOrder,
}: {
  quote: Quote;
  linked: boolean;
  mayOrder: boolean;
}) {
  const order = quote.order;
  if (order) {
    const label = (
      <>
        <PackageCheck className="size-4" aria-hidden />
        Order {order.number}
      </>
    );
    return order.url ? (
      <a
        href={order.url}
        target="_blank"
        rel="noopener"
        className={buttonClass("default")}
        title="Open the order in Bishnoi One Order"
      >
        {label}
        <ArrowUpRight className="size-4" aria-hidden />
        <span className="sr-only">(opens in a new tab)</span>
      </a>
    ) : (
      <span className="inline-flex h-9 items-center gap-2 px-2 text-sm font-medium text-ink-2">
        {label}
      </span>
    );
  }
  if (!mayOrder) return null;
  const why = !linked
    ? "Bishnoi One Order isn't connected yet. Your administrator sets ORDERS_API_URL and ORDERS_API_KEY."
    : quote.state === "waiting"
      ? "Available once the quote is approved and its guarantee letter is checked."
      : quote.state === "rejected"
        ? "A rejected quote can't be ordered."
        : quote.pharmacy?.outcome === "rejected"
          ? "The pharmacist rejected this quote's prescription, so it can't be ordered."
          : quote.pharmacy && quote.pharmacy.outcome !== "verified"
            ? "Available once a pharmacist verifies it in Pharmacy."
            : undefined;
  return (
    // The reason sits on a wrapper too: a switched-off button shows no tooltip in some browsers.
    <span title={why} className="inline-flex">
      <ConfirmButton
        label="Raise order"
        icon={<Send className="size-4" aria-hidden />}
        triggerVariant="primary"
        triggerTitle={why}
        disabled={!linked || !quote.can.order}
        danger={false}
        title={`Raise an order from ${quote.number}?`}
        body={
          <p>
            The quote&apos;s products, prices and customer are sent to Bishnoi One
            Order, which makes the sales order. This is done once per quote.
          </p>
        }
        confirmLabel="Raise order"
        onConfirm={async () => {
          const r = await raiseOrder(quote.id);
          if (!r.ok) {
            toast.error("The order wasn't raised", { description: r.error });
            return false;
          }
          toast.success(`Order ${r.data.order?.number} raised`, {
            description: "Bishnoi One Order has it now.",
          });
        }}
      />
    </span>
  );
}
