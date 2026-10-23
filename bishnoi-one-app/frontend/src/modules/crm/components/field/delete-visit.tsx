"use client";

import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { deleteVisit } from "@/src/modules/crm/actions/field";

export function DeleteVisit({ id, doctor }: { id: string; doctor: string }) {
  return (
    <ConfirmButton
      label={<span className="sr-only">Delete this visit</span>}
      icon={<Trash2 className="size-4" aria-hidden />}
      triggerVariant="quiet"
      triggerSize="sm"
      triggerTitle="Delete visit"
      triggerClassName="!px-2 !text-ink-3 hover:!text-danger"
      title="Delete this visit?"
      body={`The visit to ${doctor} goes, and so does any collection logged on it. This can't be undone.`}
      confirmLabel="Delete visit"
      onConfirm={async () => {
        const result = await deleteVisit(id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success("Visit deleted");
      }}
    />
  );
}
