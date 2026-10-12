"use client";

import { Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/platform/ui/confirm";

type Outcome = { ok: true; data: unknown } | { ok: false; error: string };

/**
 * Edit and delete for the record a page is about, as small icons beside its
 * name, so it's plain what they act on. Each names its target.
 */
export function RecordTools({ what, name, editHref, remove, after, removeNote }: {
  /** "product", "supplier"... */
  what: string;
  name: string;
  editHref?: string;
  remove?: () => Promise<Outcome>;
  /** Where to go once it's deleted. */
  after?: string;
  removeNote?: string;
}) {
  const router = useRouter();
  return (
    <>
      {editHref && (
        <Link href={editHref} title={`Edit ${what}`} className="rounded-full p-1.5 text-ink-3 hover:bg-sheet hover:text-ink">
          <Pencil className="size-4" aria-hidden />
          <span className="sr-only">Edit {what}</span>
        </Link>
      )}
      {remove && (
        <ConfirmButton
          label={<span className="sr-only">Delete {what}</span>}
          icon={<Trash2 className="size-4" aria-hidden />}
          triggerVariant="quiet"
          triggerSize="sm"
          triggerClassName="!px-1.5 !text-ink-3 hover:!text-danger"
          triggerTitle={`Delete ${what}`}
          title={`Delete ${name}?`}
          body={removeNote ?? "This can't be undone."}
          confirmLabel={`Delete ${what}`}
          onConfirm={async () => {
            const result = await remove();
            if (!result.ok) {
              toast.error(result.error);
              return false;
            }
            toast.success(`${name} deleted`);
            router.push(after ?? "/");
            return true;
          }}
        />
      )}
    </>
  );
}
