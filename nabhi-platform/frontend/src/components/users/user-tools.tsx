"use client";

import { Ban, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { updateUser } from "../../actions/users";
import { ICON_TRIGGER, ICON_TRIGGER_DANGER } from "../organizations/record-tools";

/** Suspending a person, or bringing them back, from beside their name. Their access is kept either way. */
export function SuspendUser({ id, name, status }: { id: string; name: string; status: "active" | "suspended" }) {
  const suspended = status === "suspended";
  return (
    <ConfirmButton
      label={<span className="sr-only">{suspended ? `Reactivate ${name}` : `Suspend ${name}`}</span>}
      icon={suspended ? <RotateCcw className="size-4" aria-hidden /> : <Ban className="size-4" aria-hidden />}
      triggerTitle={suspended ? `Reactivate ${name}` : `Suspend ${name}`}
      triggerVariant="quiet"
      triggerSize="sm"
      triggerClassName={suspended ? ICON_TRIGGER : ICON_TRIGGER_DANGER}
      danger={!suspended}
      title={suspended ? `Reactivate ${name}?` : `Suspend ${name}?`}
      body={
        suspended
          ? `${name} can work again, with the applications and roles they had.`
          : `${name} can't work in any application while suspended. Their applications and roles are kept, and you can reactivate them any time.`
      }
      confirmLabel={suspended ? "Reactivate" : "Suspend user"}
      onConfirm={async () => {
        const result = await updateUser(id, { status: suspended ? "active" : "suspended" });
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success(suspended ? "User reactivated" : "User suspended", { description: name });
      }}
    />
  );
}
