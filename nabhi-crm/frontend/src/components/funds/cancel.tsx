"use client";

import { toast } from "sonner";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { cancelFunds } from "../../actions/funds";

/** The requester's, until Finance releases the money. */
export function CancelFunds({ id, number }: { id: string; number: string }) {
  return (
    <ConfirmButton
      label="Cancel request"
      title={`Cancel request ${number}?`}
      body="The request will be marked as cancelled for your Team Lead and Finance. Submit a new request if the funds are needed later."
      confirmLabel="Cancel request"
      onConfirm={async () => {
        const result = await cancelFunds(id, null);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success(`${number} cancelled`);
      }}
    />
  );
}
