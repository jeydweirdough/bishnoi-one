"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { deleteMedicine, deletePatient, deleteSupplier } from "../actions/pharmacy";

const REMOVE = { medicine: deleteMedicine, patient: deletePatient, supplier: deleteSupplier };

/**
 * Delete, as a small icon beside the record's name, so it's plain the record
 * itself is what goes. The API refuses anything with history the pharmacy
 * must keep, and the reason is shown.
 */
export function DeleteRecord({ what, name, kind, id, after, body }: { what: string; name: string; kind: keyof typeof REMOVE; id: string; after: string; body?: string }) {
  const router = useRouter();
  return (
    <ConfirmButton
      label=""
      icon={<Trash2 className="size-4" aria-hidden />}
      triggerVariant="quiet"
      triggerSize="sm"
      triggerClassName="!px-2"
      triggerTitle={`Delete ${what}`}
      title={`Delete ${name}?`}
      body={body}
      confirmLabel={`Delete ${what}`}
      onConfirm={async () => {
        const result = await REMOVE[kind](id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success(`Deleted ${name}`);
        router.push(after);
        return true;
      }}
    />
  );
}
