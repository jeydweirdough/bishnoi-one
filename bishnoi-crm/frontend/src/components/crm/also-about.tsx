"use client";

import { Select } from "antd";
import { useState, useTransition } from "react";
import { findTargets } from "../../actions/associations";

/**
 * "Also about": more customers an activity is about than its own (the doctor's
 * hospital), any division's. The activity shows on each of their pages.
 */
export function AlsoAbout({ value, onChange, except }: { value: string[]; onChange: (ids: string[]) => void; except?: string }) {
  const [options, setOptions] = useState<{ value: string; label: string }[]>([]);
  const [, start] = useTransition();
  function search(q: string) {
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
      <Select
        mode="multiple"
        className="w-full"
        value={value}
        onChange={onChange}
        options={options}
        onFocus={() => options.length === 0 && search("")}
        showSearch={{ filterOption: false, onSearch: search }}
        placeholder="E.g. the hospital, so it shows there too"
        notFoundContent="Nothing by that name"
      />
    </label>
  );
}
