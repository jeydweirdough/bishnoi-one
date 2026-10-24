"use client";

import { Combobox } from "@/src/platform/ui/pickers";
import { useEffect, useRef, useState, useTransition } from "react";
import { Field } from "@/src/platform/ui/field";
import type { FormFieldDef } from "@/src/platform/lib/types";
import { findLinkOptions } from "@/src/modules/crm/actions/crm";

type Option = { value: string; label: string; teamName: string | null };

/**
 * A field that points at another customer (a doctor's hospital): search the
 * CRM's customers of the field's types, in any division, and pick one.
 */
export function CustomerPick({
  field,
  value,
  initialName,
  onChange,
  error,
}: {
  field: FormFieldDef;
  value: string;
  /** The picked customer's name, when the record already had one. */
  initialName?: string;
  onChange: (v: string) => void;
  error?: string;
}) {
  const [options, setOptions] = useState<Option[]>(value && initialName ? [{ value, label: initialName, teamName: null }] : []);
  const [loading, start] = useTransition();
  const asked = useRef(0);

  function search(q: string) {
    const mine = ++asked.current;
    start(async () => {
      const found = await findLinkOptions(field.key, q);
      if (mine !== asked.current) return;
      const next = found.map((o) => ({ value: o.id, label: o.name, teamName: o.teamName }));
      // The one already picked stays offered, so its name keeps showing.
      setOptions(value && !next.some((o) => o.value === value) ? [...options.filter((o) => o.value === value), ...next] : next);
    });
  }

  useEffect(() => search(""), []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Field label={field.label} optional={!field.required} error={error} hint={field.helpText ?? undefined}>
      {(p) => (
        <Combobox
          id={p.id}
          className="w-full"
          allowClear
          status={error ? "error" : undefined}
          value={value || undefined}
          onChange={(v) => onChange(v ?? "")}
          options={options}
          loading={loading}
          showSearch={{ filterOption: false, onSearch: search }}
          placeholder={field.placeholder ?? "Type a name to search"}
          notFoundContent={loading ? "Looking…" : `Not in the CRM yet. Add them under Customers, then pick them here.`}
          optionRender={(o) => (
            <span className="flex items-baseline justify-between gap-3">
              <span>{o.data.label}</span>
              {o.data.teamName && <span className="text-meta text-ink-3">{o.data.teamName}</span>}
            </span>
          )}
        />
      )}
    </Field>
  );
}
