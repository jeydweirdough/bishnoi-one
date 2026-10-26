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
  size,
}: {
  people: Assignable[];
  value: string;
  onChange: (id: string) => void;
  error?: string;
  label?: string;
  /** Its width in a FormGrid. */
  size?: "sm" | "md" | "lg" | "full";
}) {
  // Nobody else to give it to (a salesperson's own records): nothing to ask.
  // It's theirs, and the API makes it so when nobody is sent.
  if (people.length <= 1) return null;
  const teams = [...new Set(people.map((p) => p.team?.name ?? ""))];
  return (
    <Field label={label} size={size} error={error}>
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
