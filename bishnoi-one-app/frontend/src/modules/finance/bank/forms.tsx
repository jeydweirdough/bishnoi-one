"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { ConfirmButton } from "@/src/modules/finance/platform/ui/confirm";
import { Field, FormError, Input, Select } from "@/src/modules/finance/platform/ui/field";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { discardReconciliation, finishReconciliation, saveCleared, startReconciliation } from "@/src/modules/finance/bank/actions";
import type { BankAccount, Reconciliation } from "@/src/modules/finance/bank/types";

/** Starting a statement: which account, the statement's date and its ending balance. */
export function StartReconciliation({ accounts, org, today }: { accounts: BankAccount[]; org: Org; today: string }) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const ready = accounts.filter((a) => !a.openId);
  const [accountId, setAccountId] = useState(ready[0]?.id ?? "");
  const [date, setDate] = useState(today);
  const [balance, setBalance] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  if (!ready.length) return <p className="text-sm text-ink-2">Every account has a reconciliation in progress: open it below.</p>;
  return (
    <form
      noValidate
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        const cents = fmt.toCentavos(balance);
        if (cents === null) return setFields({ statementBalanceCentavos: "Enter the statement's ending balance." });
        start(async () => {
          const r = await startReconciliation({ accountId, statementDate: date, statementBalanceCentavos: cents });
          if (!r.ok) {
            setError(r.error);
            setFields(r.fields ?? {});
            return;
          }
          router.push(`/finance/bank/${r.data.id}`);
        });
      }}
    >
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Account" error={fields.accountId}>
          {(p) => (
            <Select {...p} value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              {ready.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} {a.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Statement date" error={fields.statementDate}>
          {(p) => <Input {...p} type="date" value={date} onChange={(e) => setDate(e.target.value)} />}
        </Field>
        <Field label="Ending balance on the statement" error={fields.statementBalanceCentavos}>
          {(p) => <Input {...p} inputMode="decimal" value={balance} onChange={(e) => setBalance(e.target.value)} />}
        </Field>
      </div>
      <FormError message={error} />
      <Button type="submit" variant="primary" loading={pending}>
        Start reconciling
      </Button>
    </form>
  );
}

/** Ticking what the bank shows, until the cleared balance is the statement's. */
export function Reconcile({ rec, org, canReconcile }: { rec: Reconciliation; org: Org; canReconcile: boolean }) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const [ticked, setTicked] = useState<Set<number>>(new Set(rec.lines.filter((l) => l.cleared).map((l) => l.id)));
  const [pending, start] = useTransition();
  const locked = rec.status !== "open" || !canReconcile;
  const totals = useMemo(() => {
    const inn = rec.lines.filter((l) => ticked.has(l.id)).reduce((t, l) => t + l.inCentavos, 0);
    const out = rec.lines.filter((l) => ticked.has(l.id)).reduce((t, l) => t + l.outCentavos, 0);
    const cleared = rec.openingBalanceCentavos + inn - out;
    return { inn, out, cleared, difference: rec.statementBalanceCentavos - cleared };
  }, [ticked, rec]);

  function toggle(id: number, on: boolean) {
    const next = new Set(ticked);
    if (on) next.add(id);
    else next.delete(id);
    setTicked(next);
  }

  function save(thenFinish: boolean) {
    start(async () => {
      const saved = await saveCleared(rec.id, [...ticked]);
      if (!saved.ok) return void toast.error(saved.error);
      if (!thenFinish) return void toast.success("Saved: continue any time");
      const done = await finishReconciliation(rec.id);
      if (!done.ok) return void toast.error(done.error);
      toast.success("Statement reconciled");
      router.push("/finance/bank");
    });
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_19rem] lg:items-start">
      <div className="overflow-x-auto rounded-[3px] border border-rule bg-sheet">
        {rec.lines.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-ink-3">Nothing on this account up to the statement&apos;s date that isn&apos;t cleared already.</p>
        ) : (
          <table className="w-full min-w-[44rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                <th className="w-10 py-2.5 pl-5 font-semibold">
                  {!locked && (
                    <input
                      type="checkbox"
                      aria-label="Tick every line"
                      checked={ticked.size === rec.lines.length}
                      onChange={(e) => setTicked(e.target.checked ? new Set(rec.lines.map((l) => l.id)) : new Set())}
                    />
                  )}
                </th>
                <th className="px-3 py-2.5 font-semibold">Date</th>
                <th className="px-3 py-2.5 font-semibold">Entry</th>
                <th className="px-3 py-2.5 font-semibold">Particulars</th>
                <th className="px-3 py-2.5 text-right font-semibold">In</th>
                <th className="py-2.5 pr-5 pl-3 text-right font-semibold">Out</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {rec.lines.map((l) => (
                <tr key={l.id} className={ticked.has(l.id) ? "bg-hema-tint/40" : ""}>
                  <td className="py-2 pl-5">
                    <input type="checkbox" aria-label={`On the statement: ${l.memo}`} checked={ticked.has(l.id)} disabled={locked} onChange={(e) => toggle(l.id, e.target.checked)} />
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">{fmt.dateLabel(l.date)}</td>
                  <td className="px-3 py-2 font-mono text-meta whitespace-nowrap">{l.number}</td>
                  <td className="px-3 py-2">
                    {l.memo}
                    {l.reference && <span className="text-ink-3"> · {l.reference}</span>}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{l.inCentavos ? fmt.peso(l.inCentavos) : ""}</td>
                  <td className="py-2 pr-5 pl-3 text-right tabular-nums">{l.outCentavos ? fmt.peso(l.outCentavos) : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <div className="space-y-3 lg:sticky lg:top-4">
        <dl className="space-y-1.5 rounded-[3px] border border-rule bg-sheet p-4 text-sm tabular-nums">
          <div className="flex justify-between"><dt className="text-ink-2">Last statement&apos;s balance</dt><dd>{fmt.peso(rec.openingBalanceCentavos)}</dd></div>
          <div className="flex justify-between"><dt className="text-ink-2">Cleared in</dt><dd>{fmt.peso(totals.inn)}</dd></div>
          <div className="flex justify-between"><dt className="text-ink-2">Cleared out</dt><dd>− {fmt.peso(totals.out)}</dd></div>
          <div className="flex justify-between border-t border-rule pt-1.5 font-semibold"><dt>Cleared balance</dt><dd>{fmt.peso(totals.cleared)}</dd></div>
          <div className="flex justify-between"><dt className="text-ink-2">Statement&apos;s balance</dt><dd>{fmt.peso(rec.statementBalanceCentavos)}</dd></div>
          <div className={`flex justify-between border-t border-ink pt-1.5 font-semibold ${totals.difference ? "text-danger" : "text-hema"}`}>
            <dt>Difference</dt>
            <dd>{fmt.peso(totals.difference)}</dd>
          </div>
          <div className="flex justify-between pt-2 text-meta text-ink-3"><dt>Book balance at the statement date</dt><dd>{fmt.peso(rec.bookBalanceCentavos)}</dd></div>
        </dl>
        {!locked && (
          <>
            {totals.difference !== 0 && (
              <p className="text-meta text-ink-3">
                A charge or interest the books don&apos;t have yet? Enter it as a journal entry, then come back and tick it.
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" loading={pending} disabled={totals.difference !== 0} onClick={() => save(true)}>
                Finish
              </Button>
              <Button loading={pending} onClick={() => save(false)}>
                Save for later
              </Button>
              <ConfirmButton
                label="Discard"
                triggerVariant="quiet"
                title="Discard this reconciliation?"
                body="Nothing in the books changes; start again any time."
                confirmLabel="Discard"
                onConfirm={async () => {
                  const r = await discardReconciliation(rec.id);
                  if (!r.ok) {
                    toast.error(r.error);
                    return false;
                  }
                  router.push("/finance/bank");
                }}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
