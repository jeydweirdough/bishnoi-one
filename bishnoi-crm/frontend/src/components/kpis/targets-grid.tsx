"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton, TextButton } from "@/src/platform/ui/button";
import { CellInput, FormError } from "@/src/platform/ui/field";
import { SectionTitle, Sheet, Empty } from "@/src/platform/ui/sheet";
import { makeFormat } from "@/src/platform/lib/format";
import type { KpiDef, KpiTargets, Org } from "@/src/platform/lib/types";
import { saveKpiTargets, type EntryChange, type TargetChange } from "../../actions/kpis";
import { kpiParse, kpiText, kpiValue } from "./words";

type Cells = Record<string, string>;
const key = (who: string, kpi: string) => `${who}|${kpi}`;

/**
 * A month's targets, a box per person (or team) and KPI. Only the KPIs that
 * apply to a person get a box. A team's box can stay empty: its people's
 * targets are added up instead (shown faintly). Manual KPIs also get their
 * results here, typed in.
 */
export function TargetsGrid({ org, data, previous, monthName, previousName, resultsHref = "/performance" }: { org: Org; data: KpiTargets; previous: KpiTargets; monthName: string; previousName: string; resultsHref?: string }) {
  const fmt = useMemo(() => makeFormat(org), [org]);
  const router = useRouter();
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const kpis = data.kpis;
  const manual = kpis.filter((k) => k.measure === "manual");
  // One role at a time: a salesperson's KPIs and a field agent's aren't the same, so they aren't one table.
  const roles = useMemo(() => {
    const count = new Map<string, { id: string; name: string; people: number }>();
    for (const p of data.people) {
      const r = count.get(p.roleId) ?? { id: p.roleId, name: p.role, people: 0 };
      r.people += 1;
      count.set(p.roleId, r);
    }
    return [...count.values()].sort((a, b) => b.people - a.people || a.name.localeCompare(b.name));
  }, [data.people]);
  const [role, setRole] = useState(roles[0]?.id ?? "");
  const forRole = (k: KpiDef) => k.roles.length === 0 || k.roles.some((r) => r.id === role);
  const shown = kpis.filter(forRole);
  const shownManual = manual.filter(forRole);
  const rolePeople = data.people.filter((p) => p.roleId === role);
  const unitOf = (id: string) => kpis.find((k) => k.id === id)!.unit;

  const fill = (src: KpiTargets): { people: Cells; teams: Cells } => {
    const people: Cells = {};
    const teams: Cells = {};
    for (const p of src.people) for (const [k, v] of Object.entries(p.targets)) if (kpis.some((x) => x.id === k)) people[key(p.person.id, k)] = kpiText(unitOf(k), v, fmt);
    for (const t of src.teams) for (const [k, v] of Object.entries(t.targets)) if (kpis.some((x) => x.id === k)) teams[key(t.team.id, k)] = kpiText(unitOf(k), v, fmt);
    return { people, teams };
  };
  const start0 = fill(data);
  const [people, setPeople] = useState<Cells>(start0.people);
  const [teams, setTeams] = useState<Cells>(start0.teams);
  const [results, setResults] = useState<Cells>(() => {
    const out: Cells = {};
    for (const p of data.people) for (const [k, v] of Object.entries(p.entries)) out[key(p.person.id, k)] = kpiText(unitOf(k), v, fmt);
    return out;
  });
  const noneYet = Object.keys(start0.people).length === 0 && Object.keys(start0.teams).length === 0;
  const hadBefore = previous.people.some((p) => Object.keys(p.targets).length) || previous.teams.some((t) => Object.keys(t.targets).length);

  function save() {
    const targets: TargetChange[] = [];
    const entries: EntryChange[] = [];
    const wrong = (k: KpiDef, who: string) => `${who}, ${k.name}: ${k.unit === "money" ? "an amount in pesos" : k.unit === "percent" ? "a whole percentage up to 100" : "a whole number"}.`;
    const original = fill(data);
    for (const p of data.people)
      for (const k of kpis) {
        if (!p.applies.includes(k.id) && !(key(p.person.id, k.id) in original.people)) continue;
        const text = people[key(p.person.id, k.id)] ?? "";
        if (text === (original.people[key(p.person.id, k.id)] ?? "")) continue;
        const v = kpiParse(k.unit, text, fmt);
        if (v === undefined) return setError(wrong(k, p.person.name));
        targets.push({ kpiId: k.id, userId: p.person.id, value: v });
      }
    for (const t of data.teams)
      for (const k of kpis) {
        const text = teams[key(t.team.id, k.id)] ?? "";
        if (text === (original.teams[key(t.team.id, k.id)] ?? "")) continue;
        const v = kpiParse(k.unit, text, fmt);
        if (v === undefined) return setError(wrong(k, t.team.name));
        targets.push({ kpiId: k.id, teamId: t.team.id, value: v });
      }
    for (const p of data.people)
      for (const k of manual) {
        const text = results[key(p.person.id, k.id)] ?? "";
        const before = p.entries[k.id] !== undefined ? kpiText(k.unit, p.entries[k.id], fmt) : "";
        if (text === before) continue;
        const v = kpiParse(k.unit, text, fmt);
        if (v === undefined) return setError(wrong(k, p.person.name));
        entries.push({ kpiId: k.id, userId: p.person.id, value: v });
      }
    if (!targets.length && !entries.length) {
      toast("Nothing changed");
      return;
    }
    start(async () => {
      const r = await saveKpiTargets(data.month, targets, entries);
      if (!r.ok) return setError(r.error);
      setError(null);
      toast.success(`Targets saved for ${monthName}`);
      router.refresh();
    });
  }

  const summed = (teamId: string, k: KpiDef) => {
    if (k.unit === "percent") return null;
    const values = data.people
      .filter((p) => p.team?.id === teamId && p.applies.includes(k.id))
      .map((p) => kpiParse(k.unit, people[key(p.person.id, k.id)] ?? "", fmt))
      .filter((v): v is number => typeof v === "number");
    return values.length ? values.reduce((s, v) => s + v, 0) : null;
  };

  const head = (
    <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
      <th scope="col" className="sticky left-0 bg-sheet py-2 pr-3 font-semibold">
        Name
      </th>
      {shown.map((k) => (
        <th key={k.id} scope="col" className="min-w-36 px-2 py-2 text-right font-semibold" title={k.description ?? undefined}>
          {k.name}
          {k.unit === "money" ? " (₱)" : k.unit === "percent" ? " (%)" : ""}
        </th>
      ))}
    </tr>
  );

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
      className="space-y-5"
    >
      {noneYet && hadBefore && (
        <p className="text-sm">
          No targets set for {monthName} yet.{" "}
          <TextButton
           
            size="inherit" className="font-semibold"
            onClick={() => {
              const before = fill(previous);
              setPeople(before.people);
              setTeams(before.teams);
            }}
          >
            Start from {previousName}&apos;s
          </TextButton>
        </p>
      )}
      {roles.length > 1 && (
        <div className="inline-flex flex-wrap gap-1 rounded-lg border border-rule bg-sheet p-1" role="tablist" aria-label="Role">
          {roles.map((r) => (
            <button
              key={r.id}
              type="button"
              role="tab"
              aria-selected={r.id === role}
              onClick={() => setRole(r.id)}
              className={`rounded-md px-3 py-1.5 text-meta ${r.id === role ? "bg-hema-tint font-semibold text-ink" : "text-ink-2 hover:bg-bench"}`}
            >
              {r.name} · {r.people}
            </button>
          ))}
        </div>
      )}
      <Sheet className="overflow-x-auto px-5 pt-3 pb-4">
        <SectionTitle>People</SectionTitle>
        {rolePeople.length === 0 ? (
          <Empty icon="goals" art="gauge" title="No measures set up" actions={<LinkButton href="/admin/settings/performance" variant="primary">Choose what is measured</LinkButton>}>Say who each measure is for under Settings → Performance, then set their targets here.</Empty>
        ) : (
          <table className="w-full text-sm">
            <thead>{head}</thead>
            <tbody className="divide-y divide-rule">
              {rolePeople.map((p) => (
                <tr key={p.person.id}>
                  <th scope="row" className="sticky left-0 bg-sheet py-2 pr-3 text-left font-medium">
                    {p.person.name}
                    <span className="block text-meta font-normal text-ink-3">
                      {p.role} · {p.team?.name ?? "No team"}
                    </span>
                  </th>
                  {shown.map((k) => (
                    <td key={k.id} className="px-2 py-2">
                      {p.applies.includes(k.id) || key(p.person.id, k.id) in start0.people ? (
                        <CellInput
                          aria-label={`${k.name} target for ${p.person.name}`}
                          inputMode={k.unit === "money" ? "decimal" : "numeric"}
                          value={people[key(p.person.id, k.id)] ?? ""}
                          onChange={(e) => setPeople({ ...people, [key(p.person.id, k.id)]: e.target.value })}
                          placeholder="No target"
                          className="text-right tabular-nums"
                        />
                      ) : (
                        <span className="block text-right text-ink-3" title={`${k.name} does not apply to ${p.role}`}>
                          —
                        </span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Sheet>

      {data.teams.length > 0 && (
        <Sheet className="overflow-x-auto px-5 pt-3 pb-4">
          <SectionTitle>Teams</SectionTitle>
          <p className="mb-2 text-meta text-ink-3">Leave a box empty to use the team&apos;s people&apos;s targets added up (shown in grey). A percentage needs its own.</p>
          <table className="w-full text-sm">
            <thead>{head}</thead>
            <tbody className="divide-y divide-rule">
              {data.teams.map((t) => (
                <tr key={t.team.id}>
                  <th scope="row" className="sticky left-0 bg-sheet py-2 pr-3 text-left font-medium">
                    {t.team.name}
                  </th>
                  {shown.map((k) => {
                    const sum = summed(t.team.id, k);
                    return (
                      <td key={k.id} className="px-2 py-2">
                        <CellInput
                          aria-label={`${k.name} target for the ${t.team.name} team`}
                          inputMode={k.unit === "money" ? "decimal" : "numeric"}
                          value={teams[key(t.team.id, k.id)] ?? ""}
                          onChange={(e) => setTeams({ ...teams, [key(t.team.id, k.id)]: e.target.value })}
                          placeholder={sum !== null ? kpiValue(k.unit, sum, fmt) : "None"}
                          className="text-right tabular-nums"
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </Sheet>
      )}

      {shownManual.length > 0 && rolePeople.length > 0 && (
        <Sheet className="overflow-x-auto px-5 pt-3 pb-4">
          <SectionTitle>Manual results</SectionTitle>
          <p className="mb-2 text-meta text-ink-3">For measures the CRM can&apos;t count: type each person&apos;s result for {monthName}.</p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Name
                </th>
                {shownManual.map((k) => (
                  <th key={k.id} scope="col" className="min-w-36 px-2 py-2 text-right font-semibold">
                    {k.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {rolePeople
                .filter((p) => shownManual.some((k) => p.applies.includes(k.id)))
                .map((p) => (
                  <tr key={p.person.id}>
                    <th scope="row" className="py-2 pr-3 text-left font-medium">
                      {p.person.name}
                    </th>
                    {shownManual.map((k) => (
                      <td key={k.id} className="px-2 py-2">
                        {p.applies.includes(k.id) ? (
                          <CellInput
                            aria-label={`${k.name} result for ${p.person.name}`}
                            inputMode={k.unit === "money" ? "decimal" : "numeric"}
                            value={results[key(p.person.id, k.id)] ?? ""}
                            onChange={(e) => setResults({ ...results, [key(p.person.id, k.id)]: e.target.value })}
                            placeholder="Not yet"
                            className="text-right tabular-nums"
                          />
                        ) : (
                          <span className="block text-right text-ink-3">—</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
            </tbody>
          </table>
        </Sheet>
      )}

      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          Save targets
        </Button>
        <LinkButton href={`${resultsHref}?month=${data.month}`} variant="quiet">
          See the results
        </LinkButton>
      </div>
    </form>
  );
}
