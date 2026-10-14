"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import type { DuplicateRecord } from "@/src/platform/lib/types";
import { markDifferent, mergeRecords } from "../../actions/duplicates";

const COUNT_WORDS: Record<string, [string, string]> = {
  contacts: ["contact", "contacts"],
  activities: ["activity", "activities"],
  quotes: ["quote", "quotes"],
  deals: ["deal", "deals"],
  visits: ["visit", "visits"],
};

function counted(counts: Record<string, number>): string {
  const said = Object.entries(counts)
    .filter(([, n]) => n > 0)
    .map(([k, n]) => `${n} ${COUNT_WORDS[k]?.[n === 1 ? 0 : 1] ?? k}`);
  return said.length ? said.join(" · ") : "Nothing on it yet";
}

/**
 * Two records that look alike, side by side. Pick the one to keep (the one
 * with more on it, to start with) and merge, or say they're different.
 */
export function DuplicatePair({
  kind,
  a,
  b,
  reasons,
  score,
  mayMerge,
  updatedLabel,
}: {
  kind: "company" | "contact";
  a: DuplicateRecord;
  b: DuplicateRecord;
  reasons: string[];
  score: number;
  mayMerge: boolean;
  updatedLabel: Record<string, string>;
}) {
  const total = (r: DuplicateRecord) => Object.values(r.counts).reduce((s, n) => s + n, 0);
  const [keep, setKeep] = useState(total(b) > total(a) ? b.id : a.id);
  const [pending, start] = useTransition();
  const kept = keep === a.id ? a : b;
  const other = keep === a.id ? b : a;
  const path = kind === "company" ? "/companies" : "/contacts";
  const noun = kind === "company" ? "customer" : "contact";

  return (
    <li className="px-5 py-4">
      <p className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-meta">
        <span className={`font-semibold ${score >= 80 ? "text-danger" : "text-due-today"}`}>{score >= 80 ? "Very likely the same" : "Possibly the same"}</span>
        <span className="text-ink-3">{reasons.join(" · ")}</span>
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {[a, b].map((r) => (
          <label
            key={r.id}
            className={`block cursor-pointer rounded-lg border px-4 py-3 ${keep === r.id ? "border-hema bg-hema/5" : "border-rule"} ${mayMerge ? "" : "cursor-default"}`}
          >
            <span className="flex items-start justify-between gap-3">
              <Link href={`${path}/${r.id}`} className="font-medium text-ink hover:underline">
                {r.name}
              </Link>
              {mayMerge && (
                <span className="flex shrink-0 items-center gap-1.5 text-meta text-ink-2">
                  <input type="radio" name={`keep-${a.id}-${b.id}`} checked={keep === r.id} onChange={() => setKeep(r.id)} className="accent-hema" />
                  Keep this record
                </span>
              )}
            </span>
            <span className="mt-1 block text-meta text-ink-3">{[r.place, r.phone, r.email].filter(Boolean).join(" · ") || "No details"}</span>
            <span className="mt-1 block text-meta text-ink-3">
              {counted(r.counts)}
              {r.owner ? ` · ${r.owner.name}'s` : ""} · changed {updatedLabel[r.id]}
            </span>
          </label>
        ))}
      </div>
      {mayMerge && (
        <div className="mt-3 flex flex-wrap gap-2">
          <ConfirmButton
            label="Merge"
            triggerVariant="primary"
            triggerSize="sm"
            title={`Merge into ${kept.name}?`}
            body={
              <>
                Everything on <b>{other.name}</b> ({counted(other.counts).toLowerCase()}) moves to <b>{kept.name}</b>, and details {kept.name} is missing are
                filled in from it. Then {other.name} is removed; links to it lead to {kept.name}. This can&apos;t be undone.
              </>
            }
            confirmLabel="Merge"
            onConfirm={async () => {
              const result = await mergeRecords(kind, kept.id, other.id);
              if (!result.ok) {
                toast.error(result.error);
                return false;
              }
              toast.success(`Merged into ${kept.name}`);
            }}
          />
          <Button
            size="sm"
            variant="quiet"
            loading={pending}
            onClick={() =>
              start(async () => {
                const result = await markDifferent(kind, a.id, b.id);
                if (!result.ok) toast.error(result.error);
                else toast.success(`Marked as different ${noun}s`);
              })
            }
          >
            Not the same
          </Button>
        </div>
      )}
    </li>
  );
}
