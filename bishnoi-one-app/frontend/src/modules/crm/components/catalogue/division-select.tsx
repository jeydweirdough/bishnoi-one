"use client";

import { useRouter } from "next/navigation";
import { Select } from "@/src/platform/ui/field";
import type { DivisionOption } from "@/src/platform/lib/types";

/** One division's promos or bundles at a time, picked from a dropdown (2026-11-23: a row of 60 chips was too much). */
export function DivisionSelect({ base, teams, current }: { base: string; teams: DivisionOption[]; current: string }) {
  const router = useRouter();
  return (
    <div className="mb-3 w-full max-w-xs">
      <Select prefix="Division" value={current} onChange={(e) => router.push(e.target.value ? `${base}?division=${e.target.value}` : base, { scroll: false })}>
        <option value="">Every division</option>
        {teams.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </Select>
    </div>
  );
}
