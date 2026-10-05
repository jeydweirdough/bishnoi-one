"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { CellInput, FormError } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import { saveRetentionRules } from "../actions/retention";
import type { RetentionRuleRow, RetentionRules } from "@/src/platform/lib/types";

type Draft = { atRisk: string; lost: string };

export function RetentionRulesEditor({ rows }: { rows: RetentionRuleRow[] }) {
  const saved = Object.fromEntries(rows.map((r) => [r.code, { atRisk: String(r.atRiskDays), lost: String(r.lostDays) }]));
  const [drafts, setDrafts] = useState<Record<string, Draft>>(saved);
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();
  const changed = rows.filter((r) => drafts[r.code].atRisk !== saved[r.code].atRisk || drafts[r.code].lost !== saved[r.code].lost);

  function save() {
    const body: Record<string, RetentionRules> = {};
    const found: Record<string, string> = {};
    for (const r of changed) {
      const atRiskDays = Number(drafts[r.code].atRisk);
      const lostDays = Number(drafts[r.code].lost);
      if (!Number.isInteger(atRiskDays) || !Number.isInteger(lostDays) || atRiskDays < 1 || lostDays > 730) {
        found[r.code] = "Whole days: at risk from 1, lost up to 730.";
      } else if (lostDays <= atRiskDays) {
        found[r.code] = "“Lost after” must be more days than “at risk after”.";
      } else body[r.code] = { atRiskDays, lostDays };
    }
    setProblems(found);
    if (Object.keys(found).length) return;
    start(async () => {
      const result = await saveRetentionRules(body);
      if (!result.ok) return setError(result.error);
      setError(null);
      toast.success("Retention rules saved", { description: "Every retention figure uses them from now on." });
    });
  }

  return (
    <Sheet className="max-w-[46rem] px-5 pt-4 pb-5">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
            <th scope="col" className="py-2 pr-3 font-semibold">Division</th>
            <th scope="col" className="px-3 py-2 font-semibold normal-case tracking-normal">At risk after</th>
            <th scope="col" className="py-2 pl-3 font-semibold normal-case tracking-normal">Lost after</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {rows.map((r) => (
            <tr key={r.code} className="align-top">
              <th scope="row" className="py-2.5 pr-3 text-left font-semibold">
                {r.name}
                {problems[r.code] && <span className="mt-1 block text-meta font-normal text-danger">{problems[r.code]}</span>}
              </th>
              {(["atRisk", "lost"] as const).map((key) => (
                <td key={key} className={key === "atRisk" ? "px-3 py-2.5" : "py-2.5 pl-3"}>
                  <span className="inline-flex items-center gap-1.5">
                    <CellInput
                      aria-label={`${r.name}: ${key === "atRisk" ? "at risk after" : "lost after"} this many days without a quote`}
                      aria-invalid={problems[r.code] ? true : undefined}
                      inputMode="numeric"
                      value={drafts[r.code][key]}
                      onChange={(e) => setDrafts({ ...drafts, [r.code]: { ...drafts[r.code], [key]: e.target.value } })}
                      className="w-20"
                    />
                    <span className="text-ink-3">days</span>
                  </span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-meta text-ink-3">
        Days without a quote. &ldquo;Lost after&rdquo; is also the window retention is measured over, so a division that buys every
        quarter should use about 90 or more.
      </p>
      <FormError message={error} />
      {changed.length > 0 && (
        <div className="animate-reshape mt-4 flex gap-2">
          <Button variant="primary" size="sm" onClick={save} loading={saving}>
            Save changes
          </Button>
          <Button variant="quiet" size="sm" onClick={() => (setDrafts(saved), setProblems({}), setError(null))} disabled={saving}>
            Discard
          </Button>
        </div>
      )}
    </Sheet>
  );
}
