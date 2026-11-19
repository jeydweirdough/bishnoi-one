"use client";

import { useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Check, CornerUpLeft, Paperclip } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, Input, Textarea } from "@/src/platform/ui/field";
import { addSlipFile, returnSlip, signSlip } from "./actions";

// What the person whose turn it is does with a slip: sign it (with an optional note) or return it (a note is
// needed); and anyone who sees a waiting slip may add a photo or document to it.

export function SlipActions({ id, number, canSign, actingAs, canAddFiles }: { id: string; number: string; canSign: boolean; actingAs: string | null; canAddFiles: boolean }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [note, setNote] = useState("");
  const [label, setLabel] = useState("");
  const file = useRef<HTMLInputElement>(null);

  function act(kind: "sign" | "return") {
    if (kind === "return" && note.trim().length < 3) return void toast.error("Say why it goes back, so they know what to change.");
    start(async () => {
      const r = kind === "sign" ? await signSlip(id, note) : await returnSlip(id, note);
      if (!r.ok) return void toast.error(r.error);
      toast.success(kind === "sign" ? (r.data.status === "approved" ? `${number} approved` : "Signed: it goes to the next step") : `${number} returned`);
      setNote("");
      router.refresh();
    });
  }

  function upload() {
    const chosen = file.current?.files?.[0];
    if (!chosen) return void toast.error("Choose a file first.");
    const form = new FormData();
    form.set("file", chosen);
    form.set("label", label.trim() || chosen.name);
    start(async () => {
      const r = await addSlipFile(id, form);
      if (!r.ok) return void toast.error(r.error);
      toast.success("File attached");
      setLabel("");
      if (file.current) file.current.value = "";
      router.refresh();
    });
  }

  if (!canSign && !canAddFiles) return null;
  return (
    <div className="mt-4 space-y-4 border-t border-rule pt-4">
      {canSign && (
        <div className="space-y-2">
          <Field label="Note" optional hint={actingAs === "administrator" ? "You act on this step as company administrator; the slip says so." : "Needed to return it; the requester sees it."}>
            {(p) => <Textarea {...p} rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />}
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" icon={<Check className="size-4" aria-hidden />} loading={busy} onClick={() => act("sign")}>
              Sign
            </Button>
            <Button icon={<CornerUpLeft className="size-4" aria-hidden />} disabled={busy} onClick={() => act("return")}>
              Return
            </Button>
          </div>
        </div>
      )}
      {canAddFiles && (
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Attach a photo or document" hint="PDF, PNG or JPEG, up to 5 MB.">
            {(p) => <input {...p} ref={file} type="file" accept="application/pdf,image/png,image/jpeg" className="block text-sm" />}
          </Field>
          <Field label="What it is" optional>
            {(p) => <Input {...p} value={label} maxLength={120} onChange={(e) => setLabel(e.target.value)} placeholder="Hospital letter" />}
          </Field>
          <Button icon={<Paperclip className="size-4" aria-hidden />} disabled={busy} onClick={upload}>
            Attach
          </Button>
        </div>
      )}
    </div>
  );
}
