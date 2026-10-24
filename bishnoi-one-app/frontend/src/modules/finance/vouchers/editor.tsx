"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { CellInput, Choice, Field, FormError, Input, Select, Textarea } from "@/src/modules/finance/platform/ui/field";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { saveVoucher, voucherChoices, voucherStep } from "@/src/modules/finance/vouchers/actions";
import type { PayableBill, Voucher, VoucherChoices, VoucherMethod } from "@/src/modules/finance/vouchers/types";

/**
 * A payment voucher (Plans/Plan - Payment vouchers): one supplier, the recorded bills it pays and
 * how much of each, how and from which account. Every bill's total, what's been paid, what other
 * vouchers set aside, what this one pays and what's left after are in plain columns, not behind a
 * click (you, 2026-10-23: part-payments must be seen).
 */
export function VoucherEditor({ voucher, choices: first, preselect, org }: { voucher: Voucher | null; choices: VoucherChoices; preselect: string | null; org: Org }) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const money = (minor: number) => String(minor / 10 ** (org.minorUnits ?? 2));
  const [choices, setChoices] = useState(first);
  const [supplierId, setSupplierId] = useState(voucher?.supplier.id ?? first.supplier?.id ?? "");
  // Ticked bills and what this voucher pays of each, as typed.
  const [paying, setPaying] = useState<Record<string, string>>(() => {
    if (voucher) return Object.fromEntries(voucher.lines.map((l) => [l.billId, money(l.amountCentavos)]));
    const b = first.bills.find((x) => x.id === preselect);
    return b ? { [b.id]: money(b.availableCentavos) } : {};
  });
  const [method, setMethod] = useState<VoucherMethod>(voucher?.method ?? "bank");
  const [paidFromId, setPaidFromId] = useState(voucher?.paidFrom?.id ?? "");
  const [oojeemaRef, setOojeemaRef] = useState(voucher?.oojeemaRef ?? "");
  const [zohoRef, setZohoRef] = useState(voucher?.zohoRef ?? "");
  const [notes, setNotes] = useState(voucher?.notes ?? "");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, load] = useTransition();
  const [pending, start] = useTransition();
  const cents = (t: string | undefined) => (t && t.trim() ? fmt.toCentavos(t) : null);

  function pickSupplier(id: string) {
    setSupplierId(id);
    setPaying({});
    if (!id) return;
    load(async () => {
      const result = await voucherChoices(id, voucher?.id ?? null);
      if (!result.ok) return setError(result.error);
      setChoices(result.data);
    });
  }

  function tick(b: PayableBill, on: boolean) {
    const next = { ...paying };
    if (on) next[b.id] = money(b.availableCentavos);
    else delete next[b.id];
    setPaying(next);
  }

  const chosen = choices.bills.filter((b) => b.id in paying);
  const total = chosen.reduce((n, b) => n + (cents(paying[b.id]) ?? 0), 0);

  function save(andSubmit: boolean) {
    const problems: Record<string, string> = {};
    if (!supplierId) problems.supplierId = "Pick the supplier.";
    if (!chosen.length) problems.lines = "Tick at least one bill to pay.";
    chosen.forEach((b) => {
      const c = cents(paying[b.id]);
      if (!c || c <= 0) problems[`bill.${b.id}`] = "Enter the amount.";
      else if (c > b.availableCentavos) problems[`bill.${b.id}`] = `At most ${fmt.peso(b.availableCentavos)}.`;
    });
    if (andSubmit && !paidFromId) problems.paidFromId = "Pick the account it's paid from.";
    if (Object.keys(problems).length) {
      setFields(problems);
      setError(problems.lines ?? "Please review the highlighted fields.");
      return;
    }
    start(async () => {
      const saved = await saveVoucher(voucher?.id ?? null, {
        supplierId,
        method,
        paidFromId: paidFromId || null,
        oojeemaRef: oojeemaRef.trim() || null,
        zohoRef: zohoRef.trim() || null,
        notes: notes.trim() || null,
        lines: chosen.map((b) => ({ billId: b.id, amountCentavos: cents(paying[b.id]) ?? 0 })),
      });
      if (!saved.ok) {
        setError(saved.error);
        setFields(saved.fields ?? {});
        return;
      }
      if (andSubmit) {
        const sent = await voucherStep(saved.data.id, "submit");
        if (!sent.ok) {
          toast.warning(`${saved.data.number} saved as a draft`, { description: sent.error });
          router.push(`/finance/vouchers/${saved.data.id}`);
          return;
        }
        toast.success(`${saved.data.number} submitted`, { description: "Waiting to be checked." });
      } else {
        toast.success(`${saved.data.number} saved as a draft`);
      }
      router.push(`/finance/vouchers/${saved.data.id}`);
    });
  }

  const s = choices.supplier;
  return (
    <form onSubmit={(e) => e.preventDefault()} noValidate className="space-y-5">
      <section className="space-y-4 rounded-[3px] border border-rule bg-sheet p-5">
        <Field label="Supplier" error={fields.supplierId} hint={choices.suppliers.length || voucher ? undefined : "No supplier has recorded bills left to pay."}>
          {(p) => (
            <Select {...p} value={supplierId} disabled={!!voucher} onChange={(e) => pickSupplier(e.target.value)}>
              <option value="">Pick a supplier…</option>
              {voucher && !choices.suppliers.some((x) => x.id === voucher.supplier.id) && <option value={voucher.supplier.id}>{voucher.supplier.name}</option>}
              {choices.suppliers.map((x) => (
                <option key={x.id} value={x.id}>
                  {x.name} · {fmt.peso(x.owedCentavos)} left to pay
                </option>
              ))}
            </Select>
          )}
        </Field>
        {supplierId && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[60rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th className="w-8 py-1.5" />
                  <th className="py-1.5 pr-2 font-semibold">Bill</th>
                  <th className="px-2 py-1.5 font-semibold">Due</th>
                  <th className="px-2 py-1.5 text-right font-semibold">To pay</th>
                  <th className="px-2 py-1.5 text-right font-semibold">Paid</th>
                  <th className="px-2 py-1.5 text-right font-semibold">In other vouchers</th>
                  <th className="w-36 px-2 py-1.5 text-right font-semibold">Pay now</th>
                  <th className="py-1.5 pl-2 text-right font-semibold">Left after</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {loading ? (
                  <tr>
                    <td colSpan={8} className="py-3 text-ink-3">
                      Loading the supplier&apos;s bills…
                    </td>
                  </tr>
                ) : choices.bills.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-3 text-ink-3">
                      No recorded bills left to pay.
                    </td>
                  </tr>
                ) : (
                  choices.bills.map((b) => {
                    const on = b.id in paying;
                    const now = on ? cents(paying[b.id]) ?? 0 : 0;
                    const left = b.payableCentavos - b.paidCentavos - now;
                    return (
                      <tr key={b.id} className={`align-top ${on ? "bg-hema-tint/30" : ""}`}>
                        <td className="py-2">
                          <input type="checkbox" aria-label={`Pay bill ${b.no}`} checked={on} disabled={!on && b.availableCentavos <= 0} onChange={(e) => tick(b, e.target.checked)} className="size-4 accent-hema" />
                        </td>
                        <td className="py-2 pr-2">
                          <span className="font-mono text-meta font-semibold">{b.no}</span> · their invoice <span className="font-mono text-meta">{b.billNumber}</span>
                          {b.documentMissing && <span className="block text-meta text-due-today">Document missing</span>}
                        </td>
                        <td className="px-2 py-2 text-ink-2">{fmt.dateLabel(b.dueDate)}</td>
                        <td className="px-2 py-2 text-right tabular-nums">{fmt.peso(b.payableCentavos)}</td>
                        <td className="px-2 py-2 text-right tabular-nums text-ink-2">{fmt.peso(b.paidCentavos)}</td>
                        <td className={`px-2 py-2 text-right tabular-nums ${b.setAsideCentavos ? "text-due-today" : "text-ink-3"}`}>{fmt.peso(b.setAsideCentavos)}</td>
                        <td className="px-2 py-2">
                          <CellInput
                            aria-label={`Pay now on bill ${b.no}`}
                            aria-invalid={fields[`bill.${b.id}`] ? true : undefined}
                            inputMode="decimal"
                            disabled={!on}
                            value={on ? paying[b.id] : ""}
                            onChange={(e) => setPaying({ ...paying, [b.id]: e.target.value })}
                            className="w-full"
                          />
                          {fields[`bill.${b.id}`] && <span className="mt-0.5 block text-right text-meta text-danger">{fields[`bill.${b.id}`]}</span>}
                        </td>
                        <td className="py-2 pl-2 text-right tabular-nums">
                          {on ? (
                            <>
                              {fmt.peso(Math.max(left, 0))}
                              <span className={`block text-meta ${left > 0 ? "font-semibold text-due-today" : "text-hema"}`}>{left > 0 ? "Partly paid" : "Paid in full"}</span>
                            </>
                          ) : (
                            <span className="text-ink-3">{fmt.peso(b.payableCentavos - b.paidCentavos)}</span>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
              <tfoot>
                <tr className="border-t border-ink font-semibold">
                  <td colSpan={6} className="py-2 text-right">
                    This voucher pays
                  </td>
                  <td className="px-2 py-2 text-right tabular-nums">{fmt.peso(total)}</td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </section>

      <section className="space-y-4 rounded-[3px] border border-rule bg-sheet p-5">
        <Choice
          name="method"
          legend="How it's paid"
          value={method}
          onChange={setMethod}
          options={choices.methods.map((m) => ({ value: m.key, label: m.label }))}
        />
        {method === "bank" && s && (
          <p className="text-meta text-ink-2">
            To: {[s.bankName, s.bankAccountName, s.bankAccountNumber].filter(Boolean).join(" · ") || <span className="text-due-today">no bank details on the supplier yet</span>}
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Paid from" error={fields.paidFromId} hint="The bank or cash account the money leaves.">
            {(p) => (
              <Select {...p} value={paidFromId} onChange={(e) => setPaidFromId(e.target.value)}>
                <option value="">Pick an account…</option>
                {choices.accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} · {a.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Oojeema PV number" optional error={fields.oojeemaRef} hint="The same voucher in Oojeema.">
            {(p) => <Input {...p} value={oojeemaRef} onChange={(e) => setOojeemaRef(e.target.value)} maxLength={60} />}
          </Field>
          <Field label="Zoho reference" optional error={fields.zohoRef} hint="The same payment in Zoho.">
            {(p) => <Input {...p} value={zohoRef} onChange={(e) => setZohoRef(e.target.value)} maxLength={60} />}
          </Field>
        </div>
        <Field label="Notes" optional error={fields.notes}>
          {(p) => <Textarea {...p} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500} />}
        </Field>
      </section>

      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" loading={pending} onClick={() => save(true)}>
          Save and submit for checking
        </Button>
        <Button loading={pending} onClick={() => save(false)}>
          Save as draft
        </Button>
        <Button variant="quiet" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
