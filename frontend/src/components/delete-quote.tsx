"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { deleteQuote } from "../actions/sales";

/**
 * `stay` is for the copy of this that sits in a customer's Quotes list: the
 * quote goes, the page it was listed on does not, so there is nowhere to send
 * anybody. Opened from the quote's own page there is — that page is the thing
 * being deleted, so it leaves for the customer it belonged to.
 */
export function DeleteQuote({
  id,
  number,
  customerId,
  stay = false,
  size,
}: {
  id: string;
  number: string;
  customerId: string;
  stay?: boolean;
  size?: "sm";
}) {
  const router = useRouter();
  return (
    <ConfirmButton
      label="Delete"
      triggerSize={size}
      title={`Delete quote ${number}?`}
      body="It and any guarantee letter attached to it are removed for everyone. This can't be undone."
      confirmLabel="Delete quote"
      onConfirm={async () => {
        const result = await deleteQuote(id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success(`Quote ${number} deleted`);
        if (!stay) router.push(`/customers/${customerId}`);
        router.refresh();
      }}
    />
  );
}
