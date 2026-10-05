"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { CellInput, FormError } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { setGoals } from "../../actions/field";
import type { FieldCounts, GoalsPayload } from "./types";
import { MEASURES } from "./words";

type Draft = Record<keyof FieldCounts, string>;
const EMPTY: Draft = { doctorsVisited: "", doctorsUpdated: "", amountCentavos: "", collectionVisits: "" };

/** A month's goals, one row per person: four boxes each. Amounts are typed in pesos. */
export function GoalsForm({ org, month, monthName, data, previous, previousName }: { org: Org; month: string; monthName: string; data: GoalsPayload; previous: GoalsPayload; previousName: string }) {
  const fmt = useMemo(() => makeFormat(org), [org]);
  const router = useRouter();
  const toDraft = (goal: FieldCounts | null): Draft =>
    goal
      ? {
          doctorsVisited: String(goal.doctorsVisited || ""),
          doctorsUpdated: String(goal.doctorsUpdated || ""),
          amountCentavos: goal.amountCentavos ? fmt.pesosText(goal.amountCentavos) : "",
          collectionVisits: String(goal.collectionVisits || ""),
        }
      : EMPTY;
  const [drafts, setDrafts] = useState<Record<string, Draft>>(() => Object.fromEntries(data.people.map((p) => [p.person.id, toDraft(p.goal)])));
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const lastMonth = new Map(previous.people.filter((p) => p.goal).map((p) => [p.person.id, p.goal]));
  const noneYet = data.people.every((p) => !p.goal);

  const set = (id: string, key: keyof FieldCounts, value: string) => setDrafts({ ...drafts, [id]: { ...drafts[id], [key]: value } });

  function save() {
    const goals: (FieldCounts & { userId: string })[] = [];
    for (const p of data.people) {
      const d = drafts[p.person.id];
      const whole = (text: string) => (text.trim() ? Number(text) : 0);
      const counts = [whole(d.doctorsVisited), whole(d.doctorsUpdated), whole(d.collectionVisits)];
      const amount = d.amountCentavos.trim() ? fmt.toCentavos(d.amountCentavos) : 0;
      if (counts.some((n) => !Number.isInteger(n) || n < 0) || amount === null) {
        setError(`${p.person.name}: goals are whole numbers, and the amount is in pesos.`);
        return;
      }
      goals.push({ userId: p.person.id, doctorsVisited: counts[0], doctorsUpdated: counts[1], collectionVisits: counts[2], amountCentavos: amount });
    }
    start(async () => {
      const result = await setGoals(month, goals);
      if (!result.ok) return setError(result.error);
      toast.success(`Goals saved for ${monthName}`);
      router.push(`/field?month=${month}`);
    });
  }

  if (data.people.length === 0) {
    return <p className="py-6 text-center text-meta text-ink-3">Nobody has the Field agent role yet. Give it to someone under People and access first.</p>;
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
    >
      {noneYet && lastMonth.size > 0 && (
        <p className="mb-3 text-sm">
          No goals set for {monthName} yet.{" "}
          <button
            type="button"
            className="font-semibold text-ink hover:underline"
            onClick={() => setDrafts(Object.fromEntries(data.people.map((p) => [p.person.id, toDraft(lastMonth.get(p.person.id) ?? null)])))}
          >
            Start from {previousName}&apos;s
          </button>
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[44rem] text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
              <th scope="col" className="py-2 pr-3 font-semibold">Person</th>
              {MEASURES.map((m) => (
                <th key={m.key} scope="col" className="px-2 py-2 font-semibold">
                  {m.label}
                  {m.money && " (₱)"}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {data.people.map((p) => (
              <tr key={p.person.id}>
                <th scope="row" className="py-2 pr-3 text-left font-medium">
                  {p.person.name}
                  <span className="block text-meta font-normal text-ink-3">{p.team?.name ?? "No team"}</span>
                </th>
                {MEASURES.map((m) => (
                  <td key={m.key} className="px-2 py-2">
                    <CellInput
                      aria-label={`${m.label} for ${p.person.name}`}
                      inputMode={m.money ? "decimal" : "numeric"}
                      value={drafts[p.person.id][m.key]}
                      onChange={(e) => set(p.person.id, m.key, e.target.value)}
                      placeholder="0"
                      className="text-right tabular-nums"
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <FormError message={error} />
      <div className="mt-4 flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          Save goals
        </Button>
        <LinkButton href={`/field?month=${month}`} variant="quiet">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}
