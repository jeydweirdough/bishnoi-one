"use client";

import { Field, Select } from "@/src/platform/ui/field";
import type { Assignable } from "@/src/platform/lib/types";

/**
 * Who a record belongs to. Only people it can be given to are offered; a role
 * that reaches only its own records has nobody else, so there's nothing to pick
 * and the field just says so.
 */
export function OwnerField({
  people,
  value,
  onChange,
  error,
  label = "Owner",
}: {
  people: Assignable[];
  value: string;
  onChange: (id: string) => void;
  error?: string;
  label?: string;
}) {
  if (people.length <= 1) {
    return (
      <div>
        <p className="mb-1 text-meta font-medium text-ink-2">{label}</p>
        <p className="flex h-9 items-center border-b border-rule text-sm">{people[0]?.isMe ? "You" : (people[0]?.name ?? "You")}</p>
      </div>
    );
  }
  const teams = [...new Set(people.map((p) => p.team?.name ?? ""))];
  return (
    <Field label={label} error={error}>
      {(p) => (
        <Select {...p} value={value} onChange={(e) => onChange(e.target.value)}>
          {teams.map((team) => (
            <optgroup key={team} label={team || "No team"}>
              {people
                .filter((x) => (x.team?.name ?? "") === team)
                .map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.name}
                    {x.isMe ? " (you)" : ""}
                  </option>
                ))}
            </optgroup>
          ))}
        </Select>
      )}
    </Field>
  );
}
