"use client";

import { Trash2, Upload } from "lucide-react";
import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Avatar, type AvatarSize } from "@/src/modules/inventory/platform/ui/avatar";
import { Button } from "@/src/modules/inventory/platform/ui/button";
import { ConfirmButton } from "@/src/modules/inventory/platform/ui/confirm";
import { FormError } from "@/src/modules/inventory/platform/ui/field";
import type { Result } from "@/src/modules/inventory/platform/lib/result";

// Choosing a picture: pick a file, see it straight away, and it uploads itself.
// Bishnoi One crops it to a square and keeps a small copy, so any photo will do.

export function PhotoPicker({
  name,
  id,
  photoAt,
  whose,
  size = "xl",
  onSave,
  onRemove,
}: {
  name: string;
  id: string;
  photoAt: string | null;
  /** "your" or the person's first name, for the wording. */
  whose: string;
  size?: AvatarSize;
  onSave: (form: FormData) => Promise<Result>;
  onRemove: () => Promise<Result>;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();

  function choose(file: File | undefined) {
    if (!file) return;
    setError(null);
    const shown = URL.createObjectURL(file);
    setPreview(shown);
    const form = new FormData();
    form.append("photo", file);
    start(async () => {
      const result = await onSave(form);
      URL.revokeObjectURL(shown);
      setPreview(null);
      if (!result.ok) {
        setError(result.fields?.photo ?? result.error);
        return;
      }
      toast.success("Photo saved");
    });
    if (input.current) input.current.value = "";
  }

  return (
    <div className="flex flex-wrap items-center gap-4">
      {preview ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={preview} alt="" aria-hidden className="size-20 shrink-0 rounded-full border border-rule object-cover opacity-70" />
      ) : (
        <Avatar name={name} id={id} photoAt={photoAt} size={size} />
      )}
      <div className="min-w-0">
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            icon={<Upload className="size-4" aria-hidden />}
            loading={saving}
            onClick={() => input.current?.click()}
          >
            {photoAt ? "Change photo" : "Add photo"}
          </Button>
          {photoAt && (
            <ConfirmButton
              label="Remove photo"
              triggerSize="sm"
              triggerVariant="quiet"
              icon={<Trash2 className="size-4" aria-hidden />}
              title={`Remove ${whose} photo?`}
              body="Initials are shown instead. A new photo can be added at any time."
              confirmLabel="Remove"
              onConfirm={async () => {
                const result = await onRemove();
                if (!result.ok) {
                  toast.error(result.error);
                  return false;
                }
                toast.success("Photo removed");
              }}
            />
          )}
        </div>
        <p className="mt-1.5 text-meta text-ink-3">JPEG, PNG or WebP, up to 6MB. Bishnoi One crops it to a square.</p>
        <FormError message={error} />
      </div>
      <input suppressHydrationWarning
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="sr-only"
        aria-label={`Pick ${whose} picture`}
        onChange={(e) => choose(e.target.files?.[0])}
      />
    </div>
  );
}
