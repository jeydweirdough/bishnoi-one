"use client";

import { Ban, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { updateCompany } from "../../actions/organizations";
import { plural } from "../../lib/words";
import { ICON_TRIGGER, ICON_TRIGGER_DANGER } from "./record-tools";

/** Suspending a company, or bringing it back, from beside its name. Nothing is deleted either way. */
export function SuspendCompany({ id, name, status, people }: { id: string; name: string; status: "active" | "suspended"; people: number }) {
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
        suspended ? (
          <>Its {plural(people, "person", "people")} can work again, with the access they had before.</>
        ) : (
          <>
            Its {plural(people, "person", "people")} can&apos;t work in any application while it&apos;s suspended. Nothing is deleted: its people, access,
            tickets and history stay, and you can reactivate it any time.
          </>
        )
      }
      confirmLabel={suspended ? "Reactivate" : "Suspend company"}
      onConfirm={async () => {
        const result = await updateCompany(id, { status: suspended ? "active" : "suspended" });
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success(suspended ? "Company reactivated" : "Company suspended", { description: name });
      }}
    />
  );
}
