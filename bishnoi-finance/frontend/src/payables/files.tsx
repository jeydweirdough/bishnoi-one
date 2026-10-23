"use client";

import { FileText, Paperclip, X } from "lucide-react";
import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { FormError } from "@/src/platform/ui/field";
import { ACCEPTED, MAX_FILE_BYTES, shrink } from "./shrink";
import type { BillFile } from "./types";

type Done = { ok: true } | { ok: false; error: string };

const size = (bytes: number) => (bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`);

/**
 * Files attached to a record, photos or PDFs: a bill's invoice (Aubrey Q6), a supplier's
 * papers. Listed with who added them; each opens in a new tab through `openBase/<id>`. With
 * `attach` and `remove` (page actions, bound to the record), they can be added and removed.
 */
export function AttachedFiles({
  files,
  openBase,
  attach,
  remove,
  empty,
  label,
}: {
  files: BillFile[];
  openBase: string;
  attach?: (form: FormData) => Promise<Done>;
  remove?: (fileId: string) => Promise<Done>;
  empty: React.ReactNode;
  label: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function upload(picked: FileList | null) {
    if (!picked?.length || !attach) return;
    start(async () => {
      setError(null);
      for (const original of Array.from(picked)) {
        const file = await shrink(original);
        if (file.size > MAX_FILE_BYTES) {
          setError(`${original.name} is over 3 MB even after making it smaller: scan or photograph it at a lower size.`);
          continue;
        }
        const form = new FormData();
        form.set("file", file);
        const result = await attach(form);
        if (!result.ok) {
          setError(`${original.name}: ${result.error}`);
          continue;
        }
        toast.success("Attached", { description: file.name });
      }
      if (input.current) input.current.value = "";
    });
  }

  return (
    <div className="space-y-3">
      {files.length ? (
        <ul className="divide-y divide-rule rounded-[3px] border border-rule">
          {files.map((f) => (
            <li key={f.id} className="flex items-center gap-3 px-3 py-2 text-sm">
              <FileText className="size-4 shrink-0 text-ink-3" aria-hidden />
              <a href={`${openBase}/${f.id}`} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate font-medium text-hema hover:underline">
                {f.name}
              </a>
              <span className="text-meta text-ink-3">
                {size(f.size)} · {f.uploadedBy}
              </span>
              {remove && (
                <ConfirmButton
                  label={<span className="sr-only">Remove {f.name}</span>}
                  icon={<X className="size-4" aria-hidden />}
                  triggerVariant="quiet"
                  triggerSize="sm"
                  title={`Remove ${f.name}?`}
                  body="The file is taken off."
                  confirmLabel="Remove"
                  onConfirm={async () => {
                    const result = await remove(f.id);
                    if (!result.ok) {
                      toast.error(result.error);
                      return false;
                    }
                  }}
                />
              )}
            </li>
          ))}
        </ul>
      ) : (
        empty
      )}
      {attach && (
        <>
          <input ref={input} type="file" accept={ACCEPTED} multiple className="sr-only" aria-label={label} onChange={(e) => upload(e.target.files)} />
          <Button icon={<Paperclip className="size-4" aria-hidden />} loading={pending} onClick={() => input.current?.click()}>
            Attach a photo or PDF
          </Button>
          <p className="text-meta text-ink-3">JPG, PNG, WebP, HEIC or PDF, up to 3 MB each. Photos are made smaller first.</p>
        </>
      )}
      <FormError message={error} />
    </div>
  );
}
