"use client";

import { Paperclip, X } from "lucide-react";
import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { ConfirmButton } from "@/src/modules/finance/platform/ui/confirm";
import { ACCEPTED, MAX_FILE_BYTES, shrink } from "@/src/modules/finance/payables/shrink";
import { attachReceipt, removeReceipt } from "@/src/modules/finance/petty-cash/actions";
import type { ReceiptFile } from "@/src/modules/finance/petty-cash/types";

/**
 * Attaching one line's receipt (a photo or a PDF, up to 3 MB), replacing it, or taking it off.
 * Photos are made smaller in the browser first, as a bill's invoice is (payables/shrink.ts).
 * Only on a saved line of a draft or returned voucher: the API keeps the file with that line.
 */
export function ReceiptSlot({ voucherId, lineId, position, file }: { voucherId: string; lineId: string; position: number; file: ReceiptFile | null }) {
  const input = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function upload(picked: FileList | null) {
    const original = picked?.[0];
    if (!original) return;
    start(async () => {
      setError(null);
      const shrunk = await shrink(original);
      if (shrunk.size > MAX_FILE_BYTES) {
        setError(`${original.name} is over 3 MB even after making it smaller: photograph or scan it at a lower size.`);
        return;
      }
      const form = new FormData();
      form.set("file", shrunk);
      const result = await attachReceipt(voucherId, lineId, form);
      if (input.current) input.current.value = "";
      if (!result.ok) return setError(result.error);
      toast.success(`Receipt ${position} attached`, { description: shrunk.name });
    });
  }

  return (
    <div className="space-y-1.5 print:hidden">
      <input suppressHydrationWarning ref={input} type="file" accept={ACCEPTED} className="sr-only" aria-label={`Attach the receipt for line ${position}`} onChange={(e) => upload(e.target.files)} />
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant={file ? "default" : "primary"} icon={<Paperclip className="size-4" aria-hidden />} loading={pending} onClick={() => input.current?.click()}>
          {file ? "Replace receipt" : "Attach receipt"}
        </Button>
        {file && (
          <ConfirmButton
            label="Remove"
            icon={<X className="size-4" aria-hidden />}
            triggerVariant="quiet"
            triggerSize="sm"
            title={`Remove the receipt on line ${position}?`}
            body="The file is taken off this line. The voucher can't be submitted until every line has its receipt again."
            confirmLabel="Remove"
            onConfirm={async () => {
              const result = await removeReceipt(voucherId, lineId);
              if (!result.ok) {
                toast.error(result.error);
                return false;
              }
            }}
          />
        )}
      </div>
      {!file && <p className="text-meta text-due-today">Receipt missing: attach a photo or PDF of it.</p>}
      <p className="text-meta text-ink-3">JPG, PNG, WebP, HEIC or PDF, up to 3 MB.</p>
      {error && (
        <p role="alert" className="text-meta text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
