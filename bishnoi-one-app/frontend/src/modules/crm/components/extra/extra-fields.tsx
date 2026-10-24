"use client";

import { AutoComplete } from "antd";
import { Combobox } from "@/src/platform/ui/pickers";
import type { ReactNode } from "react";
import { Field, Input, Select, Textarea } from "@/src/platform/ui/field";
import { FormEntityProvider } from "@/src/modules/crm/components/quick-add/can";
import { ChoiceAdd } from "@/src/modules/crm/components/quick-add/choice-add";
import { CustomerPick } from "@/src/modules/crm/components/extra/customer-pick";
import type { ExtraValues, FormFieldDef, FormLayout } from "@/src/platform/lib/types";

// A record's form, drawn from its layout (Administration → Settings → Forms):
// sections in order, each field where the admin put it. Built-in fields are
// drawn by the page (it knows how to pick an owner or a company); added fields
// are drawn here, and their values go back in `extra`.
//
// Added values are kept as the inputs hold them ("" for empty); `extraChanges`
// turns them into what the API takes: only what changed, and null for a
// cleared one.

export type ExtraDraft = Record<string, string | boolean | string[]>;

const added = (fields: FormFieldDef[]) => fields.filter((f) => !f.standard);

export function toDraft(fields: FormFieldDef[], values: ExtraValues | undefined): ExtraDraft {
  return Object.fromEntries(
    added(fields).map((f) => {
      const v = values?.[f.key];
      if (f.type === "yes_no") return [f.key, v === true];
      if (f.type === "multi_choice" || f.type === "products") return [f.key, Array.isArray(v) ? v : []];
      return [f.key, v == null ? "" : String(v)];
    }),
  );
}

type Sent = string | boolean | string[] | null;

/** What to send: everything filled (for a new record), or only what differs from `before`. */
export function extraChanges(fields: FormFieldDef[], draft: ExtraDraft, before?: ExtraValues): Record<string, Sent> | undefined {
  const out: Record<string, Sent> = {};
  for (const f of added(fields)) {
    const v = draft[f.key];
    let now: Sent;
    if (f.type === "yes_no") now = v ? true : before?.[f.key] === true ? false : null;
    else if (Array.isArray(v)) now = v.length ? v : null;
    else now = typeof v === "string" ? v.trim() || null : null;
    const was = before?.[f.key] ?? null;
    const same = JSON.stringify(now ?? "") === JSON.stringify(Array.isArray(was) ? was : was === null ? "" : typeof was === "boolean" ? was : String(was));
    if (before ? !same : now !== null) out[f.key] = now;
  }
  return Object.keys(out).length ? out : undefined;
}

/** A pick-list long enough to search, or whose choices are short codes with full names. */
const searchable = (f: FormFieldDef) => Object.keys(f.optionNames ?? {}).length > 0 || f.options.length > 7;

/**
 * A searchable pick-list. Short codes stay short ("MED ONCO"), with the full
 * name beside them in the list, and typing either finds it.
 */
export function SearchChoice({ field, value, onChange, error }: { field: FormFieldDef; value: string; onChange: (v: string) => void; error?: string }) {
  const names = field.optionNames ?? {};
  const options = [...field.options, ...(value && !field.options.includes(value) ? [value] : [])].map((o) => ({
    value: o,
    label: o,
    search: `${o} ${names[o] ?? ""}`.toLowerCase(),
    full: names[o] ?? "",
  }));
  return (
    <Field label={field.label} optional={!field.required} error={error} hint={field.helpText ?? undefined}>
      {(p) => (
        <Combobox
          id={p.id}
          aria-describedby={p["aria-describedby"]}
          status={error ? "error" : undefined}
          className="w-full"
          allowClear
          value={value || undefined}
          onChange={(v) => onChange(v ?? "")}
          placeholder={field.placeholder ?? "Type to search"}
          options={options}
          showSearch={{ filterOption: (input, option) => (option?.search ?? "").includes(input.trim().toLowerCase()) }}
          optionRender={(o) => (
            <span className="flex items-baseline justify-between gap-3">
              <span>{o.data.label}</span>
              {o.data.full && <span className="truncate text-meta text-ink-3">{o.data.full}</span>}
            </span>
          )}
          notFoundContent={<p className="px-1 py-3 text-center text-meta text-ink-3">Not one of the choices. An administrator adds choices under Settings → Forms.</p>}
        />
      )}
    </Field>
  );
}

/** One added field's input, by its kind. */
export function FieldInput({
  field,
  value,
  onChange,
  error,
  linkName,
}: {
  field: FormFieldDef;
  value: string | boolean | string[];
  onChange: (v: string | boolean | string[]) => void;
  error?: string;
  /** For a customer field: the name of the customer already picked. */
  linkName?: string;
}) {
  const f = field;
  if (f.type === "customer") {
    return <CustomerPick field={f} value={typeof value === "string" ? value : ""} initialName={linkName} onChange={onChange} error={error} />;
  }
  if (f.type === "yes_no") {
    return (
      <div className="self-end pb-2">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={value === true} onChange={(e) => onChange(e.target.checked)} className="size-4 accent-hema" />
          {f.label}
        </label>
        {f.helpText && <p className="mt-0.5 text-meta text-ink-3">{f.helpText}</p>}
        {error && <p className="mt-0.5 text-meta text-danger">{error}</p>}
      </div>
    );
  }
  if (f.type === "multi_choice") {
    const picked = Array.isArray(value) ? value : [];
    return (
      <fieldset>
        <legend className="mb-1 text-meta font-medium text-ink-2">
          {f.label} {!f.required && <span className="font-normal text-ink-3">(optional)</span>}
        </legend>
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {f.options.map((o) => (
            <label key={o} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={picked.includes(o)}
                onChange={(e) => onChange(e.target.checked ? [...picked, o] : picked.filter((x) => x !== o))}
                className="size-4 accent-hema"
              />
              {o}
            </label>
          ))}
        </div>
        {f.helpText && <p className="mt-1 text-meta text-ink-3">{f.helpText}</p>}
        {error && <p className="mt-1 text-meta text-danger">{error}</p>}
      </fieldset>
    );
  }
  if (f.type === "products") {
    const picked = Array.isArray(value) ? value : [];
    // Ours, less those left out of this field (anaesthesia isn't promoted); one already picked stays.
    const offered = (f.picks ?? []).filter((p) => !f.options.includes(p.value) || picked.includes(p.value));
    return (
      <Field label={f.label} optional={!f.required} error={error} hint={f.helpText ?? undefined}>
        {(p) => (
          <Combobox
            id={p.id}
            mode="multiple"
            className="w-full"
            status={error ? "error" : undefined}
            value={picked}
            onChange={(v) => onChange(v)}
            placeholder={f.placeholder ?? "Type a product or its generic name"}
            options={offered.map((o) => ({ value: o.value, label: o.label, search: `${o.label} ${o.hint} ${o.value}`.toLowerCase(), hint: o.hint }))}
            showSearch={{ filterOption: (input, option) => (option?.search ?? "").includes(input.trim().toLowerCase()) }}
            optionRender={(o) => (
              <span className="flex items-baseline justify-between gap-3">
                <span>{o.data.label}</span>
                {o.data.hint && <span className="truncate text-meta text-ink-3">{o.data.hint}</span>}
              </span>
            )}
            notFoundContent={<p className="px-1 py-3 text-center text-meta text-ink-3">Not one of the choices. An administrator adds choices under Settings → Forms.</p>}
          />
        )}
      </Field>
    );
  }
  const text = String(value ?? "");
  if (f.type === "molecule") {
    const q = text.trim().toLowerCase();
    return (
      <Field label={f.label} optional={!f.required} error={error} hint={f.helpText ?? undefined}>
        {(p) => (
          <AutoComplete
            id={p.id}
            className="w-full"
            status={error ? "error" : undefined}
            value={text}
            onChange={(v) => onChange(v)}
            options={(f.picks ?? []).filter((o) => !q || o.value.toLowerCase().includes(q)).map((o) => ({ value: o.value }))}
            placeholder={f.placeholder ?? "Type a generic name"}
            maxLength={120}
          />
        )}
      </Field>
    );
  }
  if (f.type === "choice" && searchable(f)) {
    return (
      <>
        <SearchChoice field={f} value={text} onChange={onChange} error={error} />
        <ChoiceAdd field={f} onAdded={onChange} />
      </>
    );
  }
  return (
    <>
    <Field label={f.label} optional={!f.required} error={error} hint={f.helpText ?? undefined}>
      {(p) =>
        f.type === "long_text" ? (
          <Textarea {...p} rows={3} value={text} onChange={(e) => onChange(e.target.value)} placeholder={f.placeholder ?? undefined} />
        ) : f.type === "choice" ? (
          <Select {...p} value={text} onChange={(e) => onChange(e.target.value)}>
            <option value="">—</option>
            {f.options.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
            {text && !f.options.includes(text) && <option value={text}>{text}</option>}
          </Select>
        ) : (
          <Input
            {...p}
            type={f.type === "date" ? "date" : f.type === "email" ? "email" : f.type === "phone" ? "tel" : "text"}
            inputMode={f.type === "number" || f.type === "money" ? "decimal" : f.type === "url" ? "url" : undefined}
            value={text}
            onChange={(e) => onChange(e.target.value)}
            placeholder={f.placeholder ?? undefined}
          />
        )
      }
    </Field>
    {f.type === "choice" && <ChoiceAdd field={f} onAdded={onChange} />}
    </>
  );
}

/** A dropdown for a built-in pick-list field (Industry, Form, Unit). A value the
 *  record already had stays offered even if it's no longer an option. */
export function ChoiceSelect({ field, value, onChange, error }: { field: FormFieldDef; value: string; onChange: (v: string) => void; error?: string }) {
  if (searchable(field)) {
    return (
      <>
        <SearchChoice field={field} value={value} onChange={onChange} error={error} />
        <ChoiceAdd field={field} onAdded={onChange} />
      </>
    );
  }
  return (
    <>
    <Field label={field.label} optional={!field.required} error={error} hint={field.helpText ?? undefined}>
      {(p) => (
        <Select {...p} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">{field.placeholder ?? "—"}</option>
          {field.options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
          {value && !field.options.includes(value) && <option value={value}>{value}</option>}
        </Select>
      )}
    </Field>
    <ChoiceAdd field={field} onAdded={onChange} />
    </>
  );
}

/**
 * The form, section by section. `standard` draws a built-in field (return null
 * to leave it out); added fields are drawn from `draft`.
 */
export function LayoutForm({
  layout,
  standard,
  draft,
  onChange,
  errors,
  linkNames = {},
}: {
  layout: FormLayout;
  standard: (field: FormFieldDef) => ReactNode;
  draft: ExtraDraft;
  onChange: (next: ExtraDraft) => void;
  errors: Record<string, string>;
  /** The names of customers its customer fields already point at, by field key. */
  linkNames?: Record<string, string>;
}) {
  return (
    <FormEntityProvider entity={layout.entity}>
      {layout.sections.map((s) => {
        // A built-in field with nothing to ask (no one else to assign to) takes no
        // space, and a section left with nothing to ask isn't shown at all.
        const asked = s.fields.filter((f) => !f.standard || standard(f) != null);
        if (asked.length === 0) return null;
        return (
        <fieldset key={s.id} className={`grid gap-5 ${s.columns === 2 ? "sm:grid-cols-2" : ""}`}>
          <legend className="mb-3 text-sm font-semibold text-ink">{s.title}</legend>
          {asked.map((f) => {
            const wide = f.type === "long_text" || f.type === "multi_choice" || f.type === "products" || f.type === "status";
            const cell = s.columns === 2 && wide ? "sm:col-span-2" : "";
            const built = f.standard ? standard(f) : null;
            return (
              <div key={f.key} className={`min-w-0 ${cell}`}>
                {f.standard ? (
                  built
                ) : (
                  <FieldInput
                    field={f}
                    value={draft[f.key] ?? ""}
                    onChange={(v) => onChange({ ...draft, [f.key]: v })}
                    error={errors[f.key]}
                    linkName={linkNames[f.key]}
                  />
                )}
              </div>
            );
          })}
        </fieldset>
        );
      })}
    </FormEntityProvider>
  );
}

/** Kept for forms that show only the added fields, without the layout's sections. */
export function ExtraFields({
  fields,
  draft,
  onChange,
  errors,
  className = "grid gap-5 sm:grid-cols-2",
}: {
  fields: FormFieldDef[];
  draft: ExtraDraft;
  onChange: (next: ExtraDraft) => void;
  errors: Record<string, string>;
  className?: string;
}) {
  const list = added(fields);
  if (list.length === 0) return null;
  return (
    <div className={className}>
      {list.map((f) => (
        <div key={f.key} className={f.type === "long_text" || f.type === "multi_choice" ? "sm:col-span-2" : ""}>
          <FieldInput field={f} value={draft[f.key] ?? ""} onChange={(v) => onChange({ ...draft, [f.key]: v })} error={errors[f.key]} />
        </div>
      ))}
    </div>
  );
}
