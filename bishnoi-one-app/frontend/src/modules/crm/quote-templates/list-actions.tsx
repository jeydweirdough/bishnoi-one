"use client";

import { FileSpreadsheet, PenLine, Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Modal } from "antd";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { createTemplate, deleteTemplate } from "@/src/modules/crm/actions/quote-templates";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";

/** Starts a template: a name and how it's made, then its page for the rest.
 *  `teams`: given to a manager, whose templates are for one of their own departments. */
export function NewTemplate({ teams }: { teams?: { id: string; name: string }[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"form" | "excel">("excel");
  const [teamId, setTeamId] = useState(teams?.length === 1 ? teams[0].id : "");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function make() {
    start(async () => {
      const r = await createTemplate({ name: name.trim(), kind, ...(teams ? { teamId: teamId || null } : {}) });
      if (!r.ok) return setError(r.error);
      setOpen(false);
      router.push(`/platform/settings/crm/quote-templates/${r.data.id}`);
    });
  }

  const option = (value: "form" | "excel", title: string, body: string, icon: React.ReactNode) => (
    <label className="flex cursor-pointer gap-3 rounded-lg border border-rule-strong p-3 has-checked:border-hema has-checked:bg-hema-tint">
      <input suppressHydrationWarning type="radio" name="kind" value={value} checked={kind === value} onChange={() => setKind(value)} className="mt-1 accent-hema" />
      <span className="text-ink-3">{icon}</span>
      <span>
        <span className="block text-sm font-semibold text-ink">{title}</span>
        <span className="block text-meta text-ink-3">{body}</span>
      </span>
    </label>
  );

  return (
    <>
      <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => (setError(null), setOpen(true))}>
        New template
      </Button>
      <Modal open={open} title="New quotation template" onCancel={() => setOpen(false)} footer={null} width={520}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            make();
          }}
          className="space-y-4"
        >
          <Field label="Name" hint="For example: PCSO, Getmeds; or Office of the President, 2MG.">
            {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} autoFocus required />}
          </Field>
          {teams && (
            <Field label="Department" hint="Your templates are for your own departments.">
              {(p) => (
                <Select {...p} value={teamId} onChange={(e) => setTeamId(e.target.value)} required>
                  <option value="">Select a department</option>
                  {teams.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
          <fieldset className="space-y-2">
            <legend className="mb-1 text-meta font-medium text-ink-2">Template type</legend>
            {option("excel", "Upload an Excel form", "Your own quotation sheet, as the issuer asks for it. The CRM fills it in for each quote.", <FileSpreadsheet className="size-5" aria-hidden />)}
            {option("form", "Design it here", "Letterhead, wording and signatory as fields. Printed from the quote.", <PenLine className="size-5" aria-hidden />)}
          </fieldset>
          <FormError message={error} />
          <div className="dialog-actions">
            <Button type="button" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={pending} disabled={name.trim().length < 2 || (!!teams && !teamId)}>
              Continue
            </Button>
          </div>
        </form>
      </Modal>
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
