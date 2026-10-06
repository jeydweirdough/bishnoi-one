"use client";

import { FileSpreadsheet, PenLine, Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { createTemplate, deleteTemplate } from "@/src/actions/quote-templates";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input } from "@/src/platform/ui/field";

/** Starts a template: a name and how it's made, then its page for the rest. */
export function NewTemplate() {
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"form" | "excel">("excel");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function make() {
    start(async () => {
      const r = await createTemplate({ name: name.trim(), kind });
      if (!r.ok) return setError(r.error);
      dialog.current?.close();
      router.push(`/admin/settings/quote-templates/${r.data.id}`);
    });
  }

  const option = (value: "form" | "excel", title: string, body: string, icon: React.ReactNode) => (
    <label className="flex cursor-pointer gap-3 rounded-[14px] border border-rule-strong p-3 has-checked:border-hema has-checked:bg-hema-tint">
      <input type="radio" name="kind" value={value} checked={kind === value} onChange={() => setKind(value)} className="mt-1 accent-hema" />
      <span className="text-ink-3">{icon}</span>
      <span>
        <span className="block text-sm font-semibold text-ink">{title}</span>
        <span className="block text-meta text-ink-3">{body}</span>
      </span>
    </label>
  );

  return (
    <>
      <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => (setError(null), dialog.current?.showModal())}>
        New template
      </Button>
      <dialog ref={dialog} className="m-auto w-full max-w-lg rounded-full bg-sheet p-0 shadow-xl backdrop:bg-black/30">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            make();
          }}
          className="space-y-4 p-5"
        >
          <h2 className="text-heading text-ink">New quotation template</h2>
          <Field label="Name" hint="For example: PCSO, Getmeds; or Office of the President, 2MG.">
            {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} autoFocus required />}
          </Field>
          <fieldset className="space-y-2">
            <legend className="mb-1 text-meta font-medium text-ink-2">How it is made</legend>
            {option("excel", "Upload an Excel form", "Your own quotation sheet, as the issuer asks for it. The CRM fills it in for each quote.", <FileSpreadsheet className="size-5" aria-hidden />)}
            {option("form", "Design it here", "Letterhead, wording and signatory as fields. Printed from the quote.", <PenLine className="size-5" aria-hidden />)}
          </fieldset>
          <FormError message={error} />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="quiet" onClick={() => dialog.current?.close()}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={pending} disabled={name.trim().length < 2}>
              Continue
            </Button>
          </div>
        </form>
      </dialog>
    </>
  );
}

export function DeleteTemplate({ id, name }: { id: string; name: string }) {
  return (
    <ConfirmButton
      label={<Trash2 className="size-3.5" aria-hidden />}
      triggerTitle={`Delete ${name}`}
      triggerVariant="quiet"
      triggerSize="sm"
      title={`Delete ${name}?`}
      body={<p>Quotes already printed keep their control numbers. Reps can no longer print with this template.</p>}
      confirmLabel="Delete template"
      onConfirm={async () => {
        const r = await deleteTemplate(id);
        if (!r.ok) {
          toast.error("Not deleted", { description: r.error });
          return false;
        }
        toast.success(`${name} deleted`);
      }}
    />
  );
}
