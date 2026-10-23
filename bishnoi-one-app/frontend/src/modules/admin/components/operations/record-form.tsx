"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { saveOperation } from "@/src/modules/admin/actions/operations";
import { FormField, ModalFrame, inputClass } from "@/src/modules/admin/components/executive-modals";
import { Button } from "@/src/modules/admin/platform/ui/button";
import type { Field, Item, Kind } from "@/src/modules/admin/components/operations/kinds";

/** What the form starts with: the record's values, or the first choice of each pick-list for a new one. */
function initial(kind: Kind, item: Item | null): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of kind.fields) {
    const v = item?.[f.key];
    out[f.key] = v == null ? (f.type === "choice" && f.options ? Object.keys(f.options)[0] : "") : String(v);
  }
  return out;
}

/** The form's values as the API takes them: numbers as numbers, blanks as nothing. */
function payload(kind: Kind, values: Record<string, string>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of kind.fields) {
    const v = values[f.key].trim();
    out[f.key] = v === "" ? null : f.type === "number" || f.type === "money" ? Number(v.replace(/,/g, "")) : v;
  }
  return out;
}

function Control({ field, value, onChange, error }: { field: Field; value: string; onChange: (v: string) => void; error?: string }) {
  const common = { value, "aria-invalid": error ? true : undefined, onChange: (e: { target: { value: string } }) => onChange(e.target.value), className: inputClass };
  if (field.type === "choice" && field.options) {
    return (
      <select {...common}>
        {Object.entries(field.options).map(([k, label]) => (
          <option key={k} value={k}>
            {label}
          </option>
        ))}
      </select>
    );
  }
  if (field.type === "long") return <textarea {...common} rows={3} placeholder={field.placeholder} />;
  return (
    <input
      {...common}
      type={field.type === "date" ? "date" : "text"}
      inputMode={field.type === "number" || field.type === "money" ? "decimal" : undefined}
      placeholder={field.placeholder}
      required={field.required}
    />
  );
}

/**
 * Adds or changes one record of any of the four lists. The API's checks come
 * back beside the field they're about.
 */
export function RecordForm({ kind, item, onClose, onSaved }: { kind: Kind; item: Item | null; onClose: () => void; onSaved: (saved: Item) => void }) {
  const [values, setValues] = useState(() => initial(kind, item));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const label = kind.one[0].toUpperCase() + kind.one.slice(1);

  function save() {
    const missing = kind.fields.filter((f) => f.required && !values[f.key].trim());
    if (missing.length) {
      setErrors(Object.fromEntries(missing.map((f) => [f.key, `${f.label} is needed.`])));
      return;
    }
    start(async () => {
      const r = await saveOperation(kind.path, item?.id ?? null, payload(kind, values));
      if (!r.ok) {
        setErrors(r.fields ?? {});
        setError(r.fields ? null : r.error);
        return;
      }
      toast.success(item ? `${label} saved` : `${label} added`, { description: kind.name(r.data as Item) });
      onSaved(r.data as Item);
      onClose();
    });
  }

  return (
    <ModalFrame title={item ? `Change ${kind.one}` : `New ${kind.one}`} subtitle={item ? kind.name(item) : kind.intro} onClose={onClose}>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
        className="space-y-5"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          {kind.fields.map((f) => (
            <div key={f.key} className={f.wide || f.type === "long" ? "sm:col-span-2" : ""}>
              <FormField label={f.label} optional={!f.required}>
                <Control field={f} value={values[f.key]} onChange={(v) => setValues({ ...values, [f.key]: v })} error={errors[f.key]} />
              </FormField>
              {errors[f.key] ? <p className="mt-1 text-meta text-danger">{errors[f.key]}</p> : f.hint ? <p className="mt-1 text-meta text-ink-3">{f.hint}</p> : null}
            </div>
          ))}
        </div>
        {error && (
          <p role="alert" className="rounded-[14px] bg-danger-tint px-3 py-2 text-meta text-danger">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2 border-t border-rule pt-4">
          <Button variant="quiet" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={pending}>
            {pending ? "Saving…" : item ? "Save changes" : `Add ${kind.one}`}
          </Button>
        </div>
      </form>
    </ModalFrame>
  );
}
