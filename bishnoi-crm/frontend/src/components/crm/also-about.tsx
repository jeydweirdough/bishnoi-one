"use client";

import { Combobox } from "@/src/platform/ui/pickers";
import { useState, useTransition } from "react";
import { findTargets } from "../../actions/associations";
import { CustomerNotFound } from "../quick-add/customer-not-found";

/**
 * "Also about": more customers an activity is about than its own (the doctor's
 * hospital), any division's. The activity shows on each of their pages.
 */
export function AlsoAbout({ value, onChange, except }: { value: string[]; onChange: (ids: string[]) => void; except?: string }) {
  const [options, setOptions] = useState<{ value: string; label: string }[]>([]);
  const [looking, start] = useTransition();
  const [typed, setTyped] = useState("");
  function search(q: string) {
    setTyped(q.trim());
    start(async () => {
      const found = (await findTargets("company", q)).filter((t) => t.id !== except);
      // The ones already picked stay offered, so their names keep showing.
      setOptions((now) => [...now.filter((o) => value.includes(o.value)), ...found.filter((t) => !value.includes(t.id)).map((t) => ({ value: t.id, label: t.hint ? `${t.name} · ${t.hint}` : t.name }))]);
    });
  }
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm text-ink">
        Also about <span className="text-ink-3">(optional)</span>
      </span>
      <Combobox
        mode="multiple"
        className="w-full"
        value={value}
        onChange={onChange}
        options={options}
        onFocus={() => options.length === 0 && search("")}
        showSearch={{ filterOption: false, onSearch: search }}
        placeholder="E.g. their organization, so it shows there too"
        notFoundContent={
          <CustomerNotFound
            typed={typed}
            loading={looking}
            onAdded={(c) => {
              setOptions((o) => [{ value: c.id, label: c.name }, ...o]);
              onChange([...value, c.id]);
            }}
          />
        }
      />
    </label>
  );
}
