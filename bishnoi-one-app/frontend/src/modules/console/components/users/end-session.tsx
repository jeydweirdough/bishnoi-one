"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/modules/console/platform/ui/confirm";
import { endSession } from "@/src/modules/console/actions/users";

/** Signing a staff session out, from its row. Ending your own signs you out here. */
export function EndSession({ id, name, yours }: { id: string; name: string; yours: boolean }) {
  const router = useRouter();
  return (
    <ConfirmButton
      label={yours ? "Sign out" : "End session"}
      triggerSize="sm"
      triggerTitle={yours ? "End your own session" : `End ${name}'s session`}
      title={yours ? "End your own session?" : `End ${name}'s session?`}
      body={
        yours
          ? "You're signed out of the console on this device and go back to the sign-in page."
          : `${name} is signed out of the console on that device and has to sign in again. Their account stays as it is.`
      }
      confirmLabel="End session"
      onConfirm={async () => {
        const result = await endSession(id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        if (yours) {
          router.replace("/login");
          return;
        }
        toast.success("Session ended", { description: name });
      }}
    />
  );
}
