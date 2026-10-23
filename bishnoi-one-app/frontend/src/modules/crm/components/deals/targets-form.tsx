"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton, TextButton } from "@/src/platform/ui/button";
import { CellInput, FormError } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org, RevenueTargets } from "@/src/platform/lib/types";
import { saveTargets } from "@/src/modules/crm/actions/deals";

/** A month's revenue targets, one box per seller, typed in pesos. An empty box is no target. */
export function TargetsForm({
  org,
  data,
  previous,
  monthName,
  previousName,
}: {
  org: Org;
  data: RevenueTargets;
  previous: RevenueTargets;
  monthName: string;
  previousName: string;
}) {
  const fmt = useMemo(() => makeFormat(org), [org]);
  const router = useRouter();
  const toText = (c: number | null | undefined) => (c ? fmt.pesosText(c) : "");
  const [drafts, setDrafts] = useState<Record<string, string>>(() => Object.fromEntries(data.people.map((p) => [p.person.id, toText(p.targetCentavos)])));
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const lastMonth = new Map(previous.people.filter((p) => p.targetCentavos).map((p) => [p.person.id, p.targetCentavos]));
  const noneYet = data.people.every((p) => !p.targetCentavos);
  const done = `/crm/deals?results=${data.month}`;

  const total = data.people.reduce((sum, p) => sum + (fmt.toCentavos(drafts[p.person.id] || "0") ?? 0), 0);

  function save() {
    const targets: { userId: string; amountCentavos: number | null }[] = [];
    for (const p of data.people) {
      const text = drafts[p.person.id].trim();
      const amount = text ? fmt.toCentavos(text) : null;
      if (text && amount === null) {
        setError(`${p.person.name}: the target is an amount in pesos.`);
        return;
      }
      targets.push({ userId: p.person.id, amountCentavos: amount || null });
    }
    start(async () => {
      const result = await saveTargets(data.month, targets);
      if (!result.ok) return setError(result.error);
      toast.success(`Revenue targets saved for ${monthName}`);
      router.push(done);
    });
  }

  if (data.people.length === 0) {
    return <p className="py-6 text-center text-meta text-ink-3">Nobody sells yet. Give someone a role that can create deals or quotes under People and access first.</p>;
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
          No targets set for {monthName} yet.{" "}
          <TextButton
           
            size="inherit" className="font-semibold"
            onClick={() => setDrafts(Object.fromEntries(data.people.map((p) => [p.person.id, toText(lastMonth.get(p.person.id))])))}
          >
            Start from {previousName}&apos;s
          </TextButton>
        </p>
      )}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
            <th scope="col" className="py-2 pr-3 font-semibold">Person</th>
            <th scope="col" className="w-48 px-2 py-2 text-right font-semibold">Target (₱)</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {data.people.map((p) => (
            <tr key={p.person.id}>
              <th scope="row" className="py-2 pr-3 text-left font-medium">
                {p.person.name}
                <span className="block text-meta font-normal text-ink-3">{p.team?.name ?? "No team"}</span>
              </th>
              <td className="px-2 py-2">
                <CellInput
                  aria-label={`Revenue target for ${p.person.name}`}
                  inputMode="decimal"
                  value={drafts[p.person.id]}
                  onChange={(e) => setDrafts({ ...drafts, [p.person.id]: e.target.value })}
                  placeholder="No target"
                  className="text-right tabular-nums"
                />
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-rule-strong">
            <th scope="row" className="py-2 pr-3 text-left font-semibold">Total</th>
            <td className="px-2 py-2 text-right font-semibold tabular-nums">{fmt.peso(total)}</td>
          </tr>
        </tfoot>
      </table>
      <FormError message={error} />
      <div className="mt-4 flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          Save targets
        </Button>
        <LinkButton href={done} variant="quiet">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}
