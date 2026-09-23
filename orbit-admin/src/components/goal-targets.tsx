"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { FormError, Input } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import { saveGoalTargets } from "../actions/goals";
import { makeFormat, percentText, toBasisPoints, type Format } from "@/src/platform/lib/format";
import type { GoalDef, GoalTargets, Org } from "@/src/platform/lib/types";
import { PickList, SaveBar } from "@/src/platform/ui/pick-list";

// What a target is counted in. Money wears the company's own mark.
const unitOf = (fmt: Format, unit: GoalDef["unit"]): string =>
  unit === "percent" ? "%" : unit === "money" ? `${fmt.symbol} a month` : unit === "count" ? "a month" : "days";

function asText(fmt: Format, goal: GoalDef, value: number): string {
  if (goal.unit === "percent") return percentText(value);
  if (goal.unit === "money") return fmt.pesosText(value);
  return String(value);
}

function fromText(fmt: Format, goal: GoalDef, text: string): number | null {
  if (goal.unit === "percent") {
    const bp = toBasisPoints(text);
    return bp !== null && bp <= 10_000 ? bp : null;
  }
  if (goal.unit === "money") return fmt.toCentavos(text);
  return /^\d{1,9}$/.test(text.trim()) ? Number(text) : null;
}

/** One division's targets at a time; the list beside it names each division's headline target. */
export function GoalTargetsEditor({ data, org }: { data: GoalTargets; org: Org }) {
  const fmt = makeFormat(org);
  const saved: Record<string, Record<string, string>> = Object.fromEntries(
    data.divisions.map((d) => [d.code, Object.fromEntries(data.goals.map((g) => [g.key, asText(fmt, g, data.targets[d.code][g.key])]))]),
  );
  const [selected, setSelected] = useState(data.divisions[0]?.code ?? "");
  const [drafts, setDrafts] = useState(saved);
  const [bad, setBad] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();

  const goalsOf = (area: string) => data.goals.filter((g) => g.area === area);
  const changedIn = (code: string) => {
    const d = data.divisions.find((x) => x.code === code);
    return d ? goalsOf(d.area).filter((g) => drafts[code][g.key] !== saved[code][g.key]) : [];
  };
  const changed = data.divisions.flatMap((d) => changedIn(d.code).map((g) => [d, g] as const));
  const division = data.divisions.find((d) => d.code === selected) ?? data.divisions[0];
  if (!division) return null;
  const goals = goalsOf(division.area);
  const sales = data.divisions.filter((d) => d.area === "sales");

  function set(goal: string, text: string) {
    setDrafts({ ...drafts, [division.code]: { ...drafts[division.code], [goal]: text } });
  }

  /** Sales divisions usually share targets: one click instead of re-typing them five times. */
  function copyToAllSales() {
    const next = { ...drafts };
    for (const d of sales) if (d.code !== division.code) next[d.code] = { ...drafts[division.code] };
    setDrafts(next);
    toast.success(`${division.name}'s targets copied to every sales division`, { description: "Save to keep them." });
  }

  function save() {
    const body: Record<string, Record<string, number>> = {};
    const wrong = new Set<string>();
    for (const [d, g] of changed) {
      const value = fromText(fmt, g, drafts[d.code][g.key]);
      if (value === null) wrong.add(`${d.code}.${g.key}`);
      else (body[d.code] ??= {})[g.key] = value;
    }
    setBad(wrong);
    if (wrong.size) {
      const first = [...wrong][0].split(".")[0];
      setSelected(first);
      return setError("Some targets aren't numbers in their unit. Percentages go up to 100.");
    }
    start(async () => {
      const result = await saveGoalTargets(body);
      if (!result.ok) return setError(result.error);
      // Written back the way the server will show them ("50000" -> "50000.00"), so nothing reads as unsaved.
      const next = { ...drafts };
      for (const [d, g] of changed) next[d.code] = { ...next[d.code], [g.key]: asText(fmt, g, body[d.code][g.key]) };
      setDrafts(next);
      setError(null);
      toast.success("Targets saved", { description: "Everyone's home page measures against them from now on." });
    });
  }

  const headline = (code: string, area: string) => {
    const first = goalsOf(area)[0];
    return first ? `${first.name} ${drafts[code][first.key]}${first.unit === "percent" ? "%" : ` ${unitOf(fmt, first.unit)}`}` : "";
  };

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[17rem_minmax(0,1fr)] lg:items-start">
      <PickList
        title="Divisions"
        icon="goals"
        items={data.divisions.map((d) => ({
          key: d.code,
          label: d.name,
          group: d.area === "sales" ? "Sales" : "Departments",
          detail: headline(d.code, d.area),
          unsaved: changedIn(d.code).length > 0,
        }))}
        selected={division.code}
        onSelect={setSelected}
      />

      <div className="min-w-0">
        <Sheet className="px-5 pt-4 pb-5">
          <h2 className="text-heading">{division.name}</h2>
          <p className="text-meta text-ink-3">
            {division.area === "sales"
              ? "Monthly counts and amounts are per person; a team's target is that times the people on it. Rates are the same for a person and a team."
              : "What this department is measured against on its home page."}
          </p>

          <ul className="mt-4 divide-y divide-rule border-y border-rule">
            {goals.map((g) => {
              const id = `goal-${division.code}-${g.key}`;
              const invalid = bad.has(`${division.code}.${g.key}`);
              return (
                <li key={g.key} className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 py-3">
                  <label htmlFor={id} className="min-w-0 flex-1">
                    <span className="block font-medium">
                      {g.name}
                      {g.better === "lower" && <span className="font-normal text-ink-3"> (at most)</span>}
                    </span>
                    <span className="block max-w-prose text-meta text-ink-3">{g.about}</span>
                  </label>
                  <span className="flex items-center gap-2 whitespace-nowrap">
                    <Input
                      id={id}
                      inputMode="decimal"
                      aria-invalid={invalid || undefined}
                      value={drafts[division.code][g.key]}
                      onChange={(e) => set(g.key, e.target.value)}
                      className="max-w-28 text-right"
                    />
                    <span className="w-20 text-meta text-ink-3">{unitOf(fmt, g.unit)}</span>
                  </span>
                </li>
              );
            })}
          </ul>

          {division.area === "sales" && sales.length > 1 && (
            <div className="mt-3">
              <Button size="sm" variant="quiet" onClick={copyToAllSales}>
                Use these for every sales division
              </Button>
            </div>
          )}
        </Sheet>

        {changed.length > 0 && (
          <SaveBar
            what={changed.length === 1 ? "1 target changed" : `${changed.length} targets changed`}
            saving={saving}
            onSave={save}
            onDiscard={() => (setDrafts(saved), setBad(new Set()), setError(null))}
            error={<FormError message={error} />}
            saveLabel="Save targets"
          />
        )}
      </div>
    </div>
  );
}
