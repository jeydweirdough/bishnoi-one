"use client";

import { Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { CellInput, Choice, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { saveBill } from "./actions";
import type { Bill, BillChoices, Supplier, VatKind } from "./types";

type Line = { key: number; accountId: string; description: string; amount: string; vat: VatKind; withholding: string };

const addDays = (day: string, n: number) => {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
};

/**
 * A supplier's bill, the way Zoho's New Bill reads (Aubrey, 2026-10-23): the supplier, their
 * invoice number and dates, what was checked, then the lines. Picking the supplier fills in
 * their terms, whether they charge VAT and the tax usually withheld. The totals below are a
 * guide while typing; the API works the bill out exactly when it's saved.
 */
export function BillEditor({ bill, choices, org }: { bill: Bill | null; choices: BillChoices; org: Org }) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const money = (minor: number) => (minor ? String(minor / 10 ** (org.minorUnits ?? 2)) : "");
  const [supplierId, setSupplierId] = useState(bill?.supplier.id ?? "");
  const supplier: Supplier | undefined = choices.suppliers.find((s) => s.id === supplierId) ?? (bill?.supplier.id === supplierId ? bill?.supplier : undefined);
  const lineFor = (key: number, s?: Supplier): Line => ({
    key,
    accountId: "",
    description: "",
    amount: "",
    vat: s && !s.vatRegistered ? "none" : "vat",
    withholding: s?.withholding?.code ?? "",
  });
  const [v, setV] = useState({
    billNumber: bill?.billNumber ?? "",
    billDate: bill?.billDate ?? choices.today,
    dueDate: bill?.dueDate ?? "",
    poNumber: bill?.poNumber ?? "",
    drNumber: bill?.drNumber ?? "",
    checkedPo: bill?.checkedPo ?? false,
    checkedDr: bill?.checkedDr ?? false,
    includeVat: bill ? (bill.amountsIncludeVat ? "yes" : "no") : "yes",
    zohoRef: bill?.zohoRef ?? "",
    oojeemaRef: bill?.oojeemaRef ?? "",
    notes: bill?.notes ?? "",
  });
  const [lines, setLines] = useState<Line[]>(
    bill?.lines.length
      ? bill.lines.map((l, i) => ({ key: i, accountId: l.accountId, description: l.description ?? "", amount: money(l.amountCentavos), vat: l.vat, withholding: l.withholding ?? "" }))
      : [lineFor(0)],
  );
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(bill?.problem ?? null);
  const [pending, start] = useTransition();
  const set = (patch: Partial<typeof v>) => setV({ ...v, ...patch });
  const setLine = (key: number, patch: Partial<Line>) => setLines(lines.map((l) => (l.key === key ? { ...l, ...patch } : l)));

  function pickSupplier(id: string) {
    setSupplierId(id);
    const s = choices.suppliers.find((x) => x.id === id);
    // Lines not filled in yet take the supplier's VAT and usual withholding.
    if (s) setLines(lines.map((l) => (l.amount.trim() || l.accountId ? l : lineFor(l.key, s))));
  }

  // A guide while typing (12%): the API works the bill out exactly when it's saved.
  const guide = lines.reduce(
    (t, l) => {
      const amount = fmt.toCentavos(l.amount) ?? 0;
      const base = l.vat === "vat" && v.includeVat === "yes" ? Math.round(amount / 1.12) : amount;
      const vat = l.vat === "vat" ? (v.includeVat === "yes" ? amount - base : Math.round(amount * 0.12)) : 0;
      const rate = choices.withholding.find((w) => w.code === l.withholding)?.rateBp ?? 0;
      const held = Math.round((base * rate) / 10_000);
      return { net: t.net + base, vat: t.vat + vat, held: t.held + held };
    },
    { net: 0, vat: 0, held: 0 },
  );
  const dueShown = v.dueDate || (supplier ? addDays(v.billDate, supplier.termsDays) : "");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const used = lines.filter((l) => l.accountId || l.amount.trim() || l.description.trim());
    const problems: Record<string, string> = {};
    if (!supplierId) problems.supplierId = "Pick the supplier.";
    if (!v.billNumber.trim()) problems.billNumber = "Enter the number on the supplier's invoice.";
    if (!used.length) problems.lines = "Add at least one line.";
    used.forEach((l, i) => {
      if (!l.accountId) problems[`lines.${i}.accountId`] = "Pick an account.";
      if (!fmt.toCentavos(l.amount)) problems[`lines.${i}.amountCentavos`] = "Enter the amount.";
    });
    if (Object.keys(problems).length) {
      setFields(problems);
      setError(problems.lines ?? "Please review the highlighted fields.");
      return;
    }
    start(async () => {
      const result = await saveBill(bill?.id ?? null, {
        supplierId,
        billNumber: v.billNumber.trim(),
        billDate: v.billDate,
        dueDate: v.dueDate || null,
        poNumber: v.poNumber.trim() || null,
        drNumber: v.drNumber.trim() || null,
        checkedPo: v.checkedPo,
        checkedDr: v.checkedDr,
        amountsIncludeVat: v.includeVat === "yes",
        zohoRef: v.zohoRef.trim() || null,
        oojeemaRef: v.oojeemaRef.trim() || null,
        notes: v.notes.trim() || null,
        lines: used.map((l) => ({
          accountId: l.accountId,
          description: l.description.trim() || null,
          amountCentavos: fmt.toCentavos(l.amount) ?? 0,
          vat: l.vat,
          withholding: l.withholding || null,
        })),
      });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success("Draft saved", { description: "Attach the supplier's invoice, then submit it for approval." });
      router.push(`/bills/${result.data.id}`);
    });
  }

  const accountsBy = (type: "expense" | "asset") => choices.accounts.filter((a) => a.type === type);

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <section className="space-y-4 rounded-[3px] border border-rule bg-sheet p-5">
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_14rem]">
          <Field
            label="Supplier"
            error={fields.supplierId}
            hint={
              choices.suppliers.length ? undefined : (
                <>
                  No suppliers yet.{" "}
                  <Link href="/suppliers/new" className="font-semibold text-hema hover:underline">
                    Add one
                  </Link>{" "}
                  first.
                </>
              )
            }
          >
            {(p) => (
              <Select {...p} value={supplierId} onChange={(e) => pickSupplier(e.target.value)}>
                <option value="">Pick a supplier…</option>
                {choices.suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                    {s.tin ? ` · ${s.tin}` : ""}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Their invoice number" error={fields.billNumber}>
            {(p) => <Input {...p} value={v.billNumber} onChange={(e) => set({ billNumber: e.target.value })} maxLength={60} placeholder="SI-004512" />}
          </Field>
        </div>
        {supplier && (
          <p className="text-meta text-ink-3">
            {supplier.vatRegistered ? "VAT-registered" : "Not VAT-registered"} · usual tax withheld:{" "}
            {supplier.withholding ? `${supplier.withholding.code} (${supplier.withholding.rateBp / 100}%)` : "none"} · terms {supplier.termsDays} days
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-4">
          <Field label="Bill date" error={fields.billDate}>
            {(p) => <Input {...p} type="date" max={choices.today} value={v.billDate} onChange={(e) => set({ billDate: e.target.value })} />}
          </Field>
          <Field label="Due date" error={fields.dueDate} hint={v.dueDate ? undefined : "From the supplier's terms."}>
            {(p) => <Input {...p} type="date" value={dueShown} onChange={(e) => set({ dueDate: e.target.value })} />}
          </Field>
          <Field label="PO number" optional error={fields.poNumber}>
            {(p) => <Input {...p} value={v.poNumber} onChange={(e) => set({ poNumber: e.target.value })} maxLength={60} />}
          </Field>
          <Field label="Delivery receipt number" optional error={fields.drNumber}>
            {(p) => <Input {...p} value={v.drNumber} onChange={(e) => set({ drNumber: e.target.value })} maxLength={60} />}
          </Field>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={v.checkedPo} onChange={(e) => set({ checkedPo: e.target.checked })} className="size-4 accent-hema" />
            Checked against the PO
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={v.checkedDr} onChange={(e) => set({ checkedDr: e.target.checked })} className="size-4 accent-hema" />
            Checked against the delivery receipt
          </label>
        </div>
      </section>

      <section className="space-y-3 rounded-[3px] border border-rule bg-sheet p-5">
        <Choice
          name="includeVat"
          legend="The amounts below"
          value={v.includeVat}
          onChange={(includeVat) => set({ includeVat })}
          options={[
            { value: "yes", label: "Include VAT (as on the invoice)" },
            { value: "no", label: "Are before VAT" },
          ]}
        />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[52rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                <th className="py-1.5 pr-2 font-semibold">Account</th>
                <th className="px-2 py-1.5 font-semibold">Description</th>
                <th className="w-32 px-2 py-1.5 font-semibold">VAT</th>
                <th className="w-44 px-2 py-1.5 font-semibold">Tax withheld</th>
                <th className="w-32 px-2 py-1.5 text-right font-semibold">Amount</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody>
              {lines.map((l, i) => (
                <tr key={l.key} className="align-top">
                  <td className="py-1.5 pr-2">
                    <select
                      aria-label={`Line ${i + 1}: account`}
                      aria-invalid={fields[`lines.${i}.accountId`] ? true : undefined}
                      value={l.accountId}
                      onChange={(e) => setLine(l.key, { accountId: e.target.value })}
                      className="h-8 w-full rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm aria-[invalid=true]:border-danger"
                    >
                      <option value="">Pick an account…</option>
                      {(["expense", "asset"] as const).map((t) =>
                        accountsBy(t).length ? (
                          <optgroup key={t} label={t === "expense" ? "Expenses" : "Assets"}>
                            {accountsBy(t).map((a) => (
                              <option key={a.id} value={a.id}>
                                {a.code} · {a.name}
                              </option>
                            ))}
                          </optgroup>
                        ) : null,
                      )}
                    </select>
                    {fields[`lines.${i}.accountId`] && <p className="mt-0.5 text-meta text-danger">{fields[`lines.${i}.accountId`]}</p>}
                  </td>
                  <td className="px-2 py-1.5">
                    <CellInput aria-label={`Line ${i + 1}: description`} value={l.description} onChange={(e) => setLine(l.key, { description: e.target.value })} maxLength={200} className="w-full !text-left" />
                  </td>
                  <td className="px-2 py-1.5">
                    <select aria-label={`Line ${i + 1}: VAT`} value={l.vat} onChange={(e) => setLine(l.key, { vat: e.target.value as VatKind })} className="h-8 w-full rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm">
                      {choices.vatKinds.map((k) => (
                        <option key={k.key} value={k.key}>
                          {k.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-2 py-1.5">
                    <select
                      aria-label={`Line ${i + 1}: tax withheld`}
                      value={l.withholding}
                      onChange={(e) => setLine(l.key, { withholding: e.target.value })}
                      className="h-8 w-full rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm"
                    >
                      <option value="">None</option>
                      {choices.withholding.map((w) => (
                        <option key={w.code} value={w.code}>
                          {w.code} · {w.rateBp / 100}%
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-2 py-1.5">
                    <CellInput
                      aria-label={`Line ${i + 1}: amount`}
                      aria-invalid={fields[`lines.${i}.amountCentavos`] ? true : undefined}
                      inputMode="decimal"
                      value={l.amount}
                      onChange={(e) => setLine(l.key, { amount: e.target.value })}
                      className="w-full"
                    />
                  </td>
                  <td className="py-1.5">
                    {lines.length > 1 && (
                      <Button size="sm" variant="quiet" className="!px-1.5 !text-ink-3 hover:!text-danger" aria-label={`Remove line ${i + 1}`} onClick={() => setLines(lines.filter((x) => x.key !== l.key))}>
                        <Trash2 className="size-4" aria-hidden />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Button size="sm" variant="quiet" className="-ml-3" icon={<Plus className="size-4" aria-hidden />} onClick={() => setLines([...lines, lineFor(Math.max(...lines.map((l) => l.key)) + 1, supplier)])}>
          Add a line
        </Button>
        <div className="ml-auto max-w-sm space-y-1 text-sm">
          <p className="flex justify-between gap-6">
            <span className="text-ink-2">Before VAT</span>
            <span className="tabular-nums">{fmt.peso(guide.net)}</span>
          </p>
          <p className="flex justify-between gap-6">
            <span className="text-ink-2">VAT</span>
            <span className="tabular-nums">{fmt.peso(guide.vat)}</span>
          </p>
          <p className="flex justify-between gap-6">
            <span className="text-ink-2">Tax withheld</span>
            <span className="tabular-nums">({fmt.peso(guide.held)})</span>
          </p>
          <p className="flex justify-between gap-6 border-t border-ink pt-1 font-semibold">
            <span>To pay the supplier</span>
            <span className="tabular-nums">{fmt.peso(guide.net + guide.vat - guide.held)}</span>
          </p>
        </div>
      </section>

      <section className="space-y-4 rounded-[3px] border border-rule bg-sheet p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Zoho reference" optional error={fields.zohoRef} hint="The same bill's number in Zoho, while both are used.">
            {(p) => <Input {...p} value={v.zohoRef} onChange={(e) => set({ zohoRef: e.target.value })} maxLength={60} />}
          </Field>
          <Field label="Oojeema reference" optional error={fields.oojeemaRef} hint="The expense or voucher number in Oojeema.">
            {(p) => <Input {...p} value={v.oojeemaRef} onChange={(e) => set({ oojeemaRef: e.target.value })} maxLength={60} />}
          </Field>
        </div>
        <Field label="Notes" optional error={fields.notes}>
          {(p) => <Textarea {...p} value={v.notes} onChange={(e) => set({ notes: e.target.value })} maxLength={500} />}
        </Field>
      </section>

      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          Save as draft
        </Button>
        <Button type="button" variant="quiet" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
