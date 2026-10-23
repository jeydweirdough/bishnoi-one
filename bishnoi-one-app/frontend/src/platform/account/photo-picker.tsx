"use client";

import { Trash2 } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Avatar, type AvatarSize } from "../ui/avatar";
import { ConfirmButton } from "../ui/confirm";
import { FileDrop } from "../ui/file-drop";
import { FormError } from "../ui/field";
import type { Result } from "../lib/result";

// Choosing a picture: drop it on the box (or browse), see it straight away, and it uploads itself.
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
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();
  // A new drop zone after each save, so it's ready for the next picture rather than showing the last.
  const [round, setRound] = useState(0);

  function choose(file: File | null) {
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
      setRound((n) => n + 1);
      if (!result.ok) {
        setError(result.fields?.photo ?? result.error);
        return;
      }
      toast.success("Photo saved");
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview} alt="" aria-hidden className="size-20 shrink-0 rounded-full border border-rule object-cover opacity-70" />
        ) : (
          <Avatar name={name} id={id} photoAt={photoAt} size={size} />
        )}
        <div className="min-w-0 text-meta text-ink-3">
          <p>{saving ? "Saving the picture…" : photoAt ? "Drop a new one below to change it." : "No picture yet: your initials show instead."}</p>
          {photoAt && !saving && (
            <ConfirmButton
              label="Remove picture"
              triggerSize="sm"
              triggerVariant="quiet"
              icon={<Trash2 className="size-4" aria-hidden />}
              title={`Remove ${whose} photo?`}
              body="Initials take its place. A new one can be added any time."
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
      </div>
      <FileDrop
        key={round}
        accept="image/jpeg,image/png,image/webp"
        note="JPEG, PNG or WebP, up to 6 MB. Bishnoi One crops it to a square."
        maxBytes={6 * 1024 * 1024}
        busy={saving}
        keep
        onFile={choose}
      />
      <FormError message={error} />
    </div>
  );
}
