"use client";

import { PackageCheck, Send } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { raiseOrder } from "@/src/modules/crm/actions/quote-order";
import { buttonClass } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import type { Quote } from "@/src/platform/lib/types";

const STATUS: Record<string, string> = {
  sent: "Sent to Sales", pending: "Waiting for approval", confirmed: "Confirmed", delivered: "Delivered", rejected: "Rejected", cancelled: "Cancelled",
};

/** Raise this quote's sales order (feature plan step 11).
 *
 *  The order details go to the Sales app (as the event quote.ordered, through Bishnoi One); the order is made
 *  there, waits for approval, and its number and progress come back here. A quote is ordered once; after that
 *  this shows the order, linking to it, with its status instead of the button.
 *
 *  Shown to people who raise orders. Until the quote is approved and its letter checked (and an Rx quote
 *  verified), the button is there but off, and says why on hover. */
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
    // Once it ships, where the delivery is says more than the order's status (step 12).
    // Then invoiced and paid (step 13): the end of the chain.
    const status = order.invoice?.paidAt ? "Paid" : order.invoice?.number ? `Invoiced ${order.invoice.number}` : (order.delivery?.statusLabel ?? STATUS[order.status ?? "sent"] ?? order.status);
    const tracking = order.delivery?.trackingNumber ? (
      order.delivery.trackingUrl ? (
        <a href={order.delivery.trackingUrl} target="_blank" rel="noreferrer" className="text-meta text-hema hover:underline">
          {order.delivery.courier ?? "Courier"} {order.delivery.trackingNumber}
        </a>
      ) : (
        <span className="text-meta text-ink-3">
          {order.delivery.courier ?? "Courier"} {order.delivery.trackingNumber}
        </span>
      )
    ) : null;
    const label = (
      <>
        <PackageCheck className="size-4" aria-hidden />
        {order.number ? `Order ${order.number}` : "Order sent"}
        <span className="text-meta font-normal text-ink-3">· {status}</span>
      </>
    );
    return order.url && order.id ? (
      <span className="inline-flex flex-wrap items-center gap-2">
        <Link href={order.url} className={buttonClass("default")} title={order.note ? `${status}: ${order.note}` : `Open the sales order (${status.toLowerCase()})`}>
          {label}
        </Link>
        {tracking}
      </span>
    ) : (
      <span className="inline-flex h-9 items-center gap-2 px-2 text-sm font-medium text-ink-2" title="The Sales app is making the order; its number shows here in a moment.">
        {label}
      </span>
    );
  }
  if (!mayOrder) return null;
  const why = !linked
    ? "Sales isn't available for your company yet. Ask your administrator to turn it on in Apps."
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
            The quote&apos;s products, prices and customer go to Sales, which makes the sales order. It
            waits for approval there; its number and progress show here. This is done once per quote.
          </p>
        }
        confirmLabel="Raise order"
        onConfirm={async () => {
          const r = await raiseOrder(quote.id);
          if (!r.ok) {
            toast.error("The order wasn't raised", { description: r.error });
            return false;
          }
          toast.success("Order sent to Sales", {
            description: "It waits for approval there; its number shows here in a moment.",
          });
        }}
      />
    </span>
  );
}
