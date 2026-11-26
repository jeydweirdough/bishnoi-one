"use client";

import { Flag } from "@/src/platform/ui/marks";
import { Combobox } from "@/src/platform/ui/pickers";
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
        <span key={t.id} className="inline-flex h-6 items-center rounded-md border border-ink px-2.5 text-meta font-medium whitespace-nowrap text-ink">
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
        // A dropdown with every division ticked or not, Select all and Clear (2026-11-23, owner: the row of chips was too
        // much with 60 divisions): for every division, Select all; for all but a few, Select all and untick those.
        <div className="max-w-xl">
          <Combobox<string[]>
            mode="multiple"
            options={options.map((o) => ({ value: o.id, label: o.name }))}
            value={value.filter((id) => options.some((o) => o.id === id))}
            onChange={(ids) => onChange([...kept, ...ids])}
            placeholder="Pick the divisions"
            allLabel="All divisions"
            aria-invalid={Boolean(error)}
            aria-label="Divisions"
          />
          {kept.length > 0 && <p className="mt-1 text-meta text-ink-3">And {kept.length} switched-off division(s), kept.</p>}
        </div>
      )}
      {error && <p className="mt-1 text-meta text-danger">{error}</p>}
    </fieldset>
  );
}
