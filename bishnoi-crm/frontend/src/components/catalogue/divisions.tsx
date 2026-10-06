"use client";

import { Flag } from "@/src/platform/ui/marks";
import type { DivisionOption } from "@/src/platform/lib/types";

/**
 * Promos and bundles are per division: a B2C promo isn't seen or quoted in
 * B2B, HOS or any other. These are the two pieces that say so on screen.
 */

/** Which divisions it's for, on a promo's or bundle's row. None: nobody can quote it. */
export function DivisionTags({ teams }: { teams: DivisionOption[] }) {
  if (teams.length === 0) return <Flag letter="!">No division yet: nobody can quote it</Flag>;
  return (
    <span className="inline-flex flex-wrap gap-1">
      {teams.map((t) => (
        <span key={t.id} className="inline-flex h-6 items-center rounded-full border border-ink px-2.5 text-meta font-medium whitespace-nowrap text-ink">
          {t.name}
        </span>
      ))}
    </span>
  );
}

/** Picking the divisions, on the form. Someone with only their own division just sees it named. */
export function DivisionPicker({
  options,
  value,
  onChange,
  error,
  what,
}: {
  options: DivisionOption[];
  value: string[];
  onChange: (ids: string[]) => void;
  error?: string;
  what: "promo" | "bundle";
}) {
  // Kept on the form even if it's one this person can't pick now (a switched-off team).
  const kept = value.filter((id) => !options.some((o) => o.id === id));
  return (
    <fieldset>
      <legend className="mb-1 text-sm font-semibold">Divisions</legend>
      <p className="mb-2 text-meta text-ink-3">Only these divisions see this {what} and can quote it.</p>
      {options.length === 1 && value.length === 1 && value[0] === options[0].id ? (
        <p className="text-sm">{options[0].name}</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {options.map((o) => (
            <label
              key={o.id}
              className="relative inline-flex cursor-pointer items-center gap-1.5 rounded-[14px] border border-rule-strong px-3 py-1.5 text-meta text-ink-2 has-checked:border-hema has-checked:bg-hema-tint has-checked:font-semibold has-checked:text-ink has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-hema"
            >
              <input
                type="checkbox"
                className="sr-only"
                checked={value.includes(o.id)}
                onChange={(e) => onChange(e.target.checked ? [...value, o.id] : value.filter((id) => id !== o.id))}
              />
              {o.name}
            </label>
          ))}
          {kept.length > 0 && <span className="self-center text-meta text-ink-3">and {kept.length} switched-off division(s)</span>}
        </div>
      )}
      {error && <p className="mt-1 text-meta text-danger">{error}</p>}
    </fieldset>
  );
}
