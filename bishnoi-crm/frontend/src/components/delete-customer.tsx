"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { deleteCustomer } from "../actions/customers";

export function DeleteCustomer({ id, name }: { id: string; name: string }) {
  const router = useRouter();
  return (
    <ConfirmButton
      label="Delete"
      title={`Delete ${name}?`}
      body="Their calls, visits, notes and follow-ups are deleted too, for everyone. This can't be undone."
      confirmLabel="Delete customer"
      onConfirm={async () => {
        const result = await deleteCustomer(id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success(`${name} deleted`);
        router.push("/customers");
        router.refresh();
      }}
    />
  );
}
