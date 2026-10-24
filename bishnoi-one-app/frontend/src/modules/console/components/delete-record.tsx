"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/modules/console/platform/ui/confirm";
import { deleteRecord, type Deletable } from "@/src/modules/console/actions/deletes";
import { ICON_TRIGGER_DANGER } from "@/src/modules/console/components/organizations/record-tools";

/**
 * The trash button beside a record's name: asks first, saying what goes with
 * it, then deletes it and, from its own page, goes back to the list (`after`).
 */
export function DeleteRecord({ kind, id, name, body, after, done = "Deleted" }: { kind: Deletable; id: string; name: string; body: ReactNode; after?: string; done?: string }) {
  const router = useRouter();
  return (
    <ConfirmButton
      label={<span className="sr-only">Delete {name}</span>}
      icon={<Trash2 className="size-4" aria-hidden />}
      triggerTitle={`Delete ${name}`}
      triggerVariant="quiet"
      triggerSize="sm"
      triggerClassName={ICON_TRIGGER_DANGER}
      title={`Delete ${name}?`}
      body={body}
      confirmLabel="Delete"
      onConfirm={async () => {
        const result = await deleteRecord(kind, id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success(done, { description: name });
        if (after) router.push(after);
      }}
    />
  );
}
