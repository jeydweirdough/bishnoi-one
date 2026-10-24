"use client";

import { PackageCheck, Plus, Search, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { CellInput, Field, FormError, Input, Select, Textarea } from "@/src/modules/finance/platform/ui/field";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { findSuppliers, saveBill, supplierDeliveries } from "@/src/modules/finance/bills/actions";
import type { Bill, BillSetup, BillSupplier, Delivery } from "@/src/modules/finance/bills/types";

type Line = { key: number; description: string; accountId: string; kind: string; amount: string; withheld: boolean };

/**
 * A supplier's invoice, recorded as a draft: which of Inventory's suppliers,
 * their invoice number and date, what it's for (each line to an account, by its
 * VAT kind), and the tax withheld from them (its ATC). The API works out the
 * input VAT and the withholding when it's saved; the bill's page records it.
 */
export function BillEditor({ bill, setup, org, today }: { bill: Bill | null; setup: BillSetup; org: Org; today: string }) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const minor = 10 ** (org.minorUnits ?? 2);
  const defaultAccount = setup.accounts.find((a) => a.type === "expense")?.id ?? setup.accounts[0]?.id ?? "";
  const [supplier, setSupplier] = useState<BillSupplier | null>(bill?.supplier ?? null);
  const [invoiceNo, setInvoiceNo] = useState(bill?.supplierInvoiceNo ?? "");
  const [date, setDate] = useState(bill?.billDate ?? today);
  const [terms, setTerms] = useState(String(bill?.termsDays ?? 30));
  const [deliveryRef, setDeliveryRef] = useState(bill?.deliveryRef ?? "");
  const [notes, setNotes] = useState(bill?.notes ?? "");
  const [includeVat, setIncludeVat] = useState(bill?.amountsIncludeVat ?? true);
  const [atc, setAtc] = useState(bill?.atc ?? "");
  const [rate, setRate] = useState(bill?.atc ? String(bill.ewtRateBp / 100) : "");
  const blank = (key: number, kind = "vatable"): Line => ({ key, description: "", accountId: defaultAccount, kind, amount: "", withheld: true });
  const [lines, setLines] = useState<Line[]>(
    bill?.computed?.lines.length
      ? bill.computed.lines.map((l, i) => ({ key: i, description: l.description, accountId: l.accountId, kind: l.kind, amount: String(l.amountCentavos / minor), withheld: l.withheld }))
      : [blank(0)],
  );
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const set = (key: number, patch: Partial<Line>) => setLines(lines.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  const nonVat = supplier?.vatStatus === "non_vat";

  // Finding the supplier in Inventory, and what they delivered.
  const [q, setQ] = useState("");
  const [found, setFound] = useState<BillSupplier[] | null>(null);
  const [deliveries, setDeliveries] = useState<Delivery[] | null>(null);
  const [searching, search] = useTransition();
  function lookUp() {
    search(async () => {
      const result = await findSuppliers(q.trim());
      if (!result.ok) return void toast.error(result.error);
      setFound(result.data);
    });
  }
  function pick(s: BillSupplier) {
    setSupplier(s);
    setFound(null);
    setQ("");
    if (s.defaultAtc && !atc) {
      setAtc(s.defaultAtc);
      const known = setup.atcs.find((a) => a.code === s.defaultAtc);
      if (known) setRate(String(known.rateBp / 100));
    }
    if (s.vatStatus === "non_vat") setLines(lines.map((l) => ({ ...l, kind: "non_vat" })));
    search(async () => {
      const result = await supplierDeliveries(s.id);
      setDeliveries(result.ok ? result.data : []);
    });
  }
  function fromDelivery(d: Delivery) {
    setDeliveryRef(d.number);
    setLines(d.lines.map((l, i) => ({ key: Date.now() + i, description: `${l.product} (${l.sku}) × ${l.quantity}`, accountId: defaultAccount, kind: nonVat ? "non_vat" : "vatable", amount: String(l.amount / minor), withheld: true })));
    setDeliveries(null);
    toast.success(`Lines taken from delivery ${d.number}. Check the amounts against the supplier's invoice.`);
  }
  function pickAtc(code: string) {
    setAtc(code);
    const known = setup.atcs.find((a) => a.code === code);
    setRate(code ? String((known?.rateBp ?? 0) / 100) : "");
  }

  // What it comes to, as the API will work it out (12% VAT): shown while typing.
  const rateBp = Math.round(Number(rate || 0) * 100);
  const preview = lines.reduce(
    (t, l) => {
      const amount = fmt.toCentavos(l.amount) ?? 0;
      const net = l.kind === "vatable" ? (includeVat ? Math.round((amount * 10000) / 11200) : amount) : amount;
      const vat = l.kind === "vatable" ? (includeVat ? amount - net : Math.round(amount * 0.12)) : 0;
      return { net: t.net + net, vat: t.vat + vat, base: t.base + (atc && l.withheld ? net : 0) };
    },
    { net: 0, vat: 0, base: 0 },
  );
  const ewt = atc ? Math.round((preview.base * rateBp) / 10000) : 0;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const used = lines.filter((l) => l.description.trim() || l.amount.trim());
    const problems: Record<string, string> = {};
    if (!supplier) problems.supplierId = "Pick the supplier.";
    if (!invoiceNo.trim()) problems.supplierInvoiceNo = "Enter the supplier's invoice number.";
    if (!used.length) problems.lines = "Add at least one line.";
    used.forEach((l, i) => {
      if (!l.description.trim()) problems[`lines.${i}.description`] = "Say what it's for.";
      if (fmt.toCentavos(l.amount) === null) problems[`lines.${i}.amountCentavos`] = "Enter the amount.";
    });
    if (Object.keys(problems).length) {
      setFields(problems);
      setError(problems.lines ?? "Please review the highlighted fields.");
      return;
    }
    start(async () => {
      const result = await saveBill(bill?.id ?? null, {
        supplierId: supplier!.id,
        supplierInvoiceNo: invoiceNo.trim(),
        billDate: date,
        termsDays: Number(terms) || 0,
        deliveryRef: deliveryRef.trim() || null,
        notes: notes.trim() || null,
        amountsIncludeVat: includeVat,
        lines: used.map((l) => ({ description: l.description.trim(), accountId: l.accountId, kind: l.kind, amountCentavos: fmt.toCentavos(l.amount) ?? 0, withheld: l.withheld })),
        atc: atc || null,
        ewtRateBp: atc ? rateBp : null,
      });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success("Draft saved");
      router.push(`/finance/bills/${result.data.id}`);
    });
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <section className="space-y-4 rounded-[3px] border border-rule bg-sheet p-5">
        <p className="text-sm font-semibold">Supplier</p>
        <div className="flex gap-2">
          <Input
            aria-label="Find a supplier in Inventory"
            placeholder="Find a supplier in Inventory: name or code"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                lookUp();
              }
            }}
          />
          <Button type="button" icon={<Search className="size-4" aria-hidden />} loading={searching} onClick={lookUp}>
            Find
          </Button>
        </div>
        {fields.supplierId && <p className="text-meta text-danger">{fields.supplierId}</p>}
        {found && (
          <ul className="divide-y divide-rule rounded-[3px] border border-rule">
            {found.length === 0 && <li className="px-3 py-2 text-meta text-ink-3">No supplier matches. Suppliers are added in Inventory.</li>}
            {found.map((s) => (
              <li key={s.id}>
                <button type="button" onClick={() => pick(s)} className="w-full px-3 py-2 text-left text-sm hover:bg-hema-tint">
                  <span className="font-semibold">{s.name}</span>
                  <span className="text-ink-3"> · {s.tin ? `TIN ${s.tin}` : "no TIN in Inventory"} · {s.vatStatus === "non_vat" ? "non-VAT" : "VAT-registered"}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {supplier && (
          <div className="rounded-[3px] bg-bench/60 px-3 py-2 text-sm">
            <span className="font-semibold">{supplier.name}</span>
            <span className="text-ink-2"> · {supplier.tin ? `TIN ${supplier.tin}` : <span className="text-danger">no TIN: add it to the supplier in Inventory</span>} · {nonVat ? "not VAT-registered" : "VAT-registered"}</span>
            {supplier.address && <span className="text-ink-3"> · {supplier.address}</span>}
          </div>
        )}
        {deliveries && deliveries.length > 0 && (
          <div>
            <p className="mb-1 text-meta text-ink-2">Start from a delivery received in Inventory:</p>
            <ul className="flex flex-wrap gap-2">
              {deliveries.slice(0, 8).map((d) => (
                <li key={d.id}>
                  <Button type="button" size="sm" icon={<PackageCheck className="size-4" aria-hidden />} onClick={() => fromDelivery(d)}>
                    {d.number}
                    {d.order ? ` (${d.order})` : ""} · {fmt.peso(d.totalCost)}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="grid gap-4 sm:grid-cols-4">
          <Field label="Supplier's invoice no." error={fields.supplierInvoiceNo}>
            {(p) => <Input {...p} value={invoiceNo} onChange={(e) => setInvoiceNo(e.target.value)} maxLength={60} />}
          </Field>
          <Field label="Invoice date" error={fields.billDate}>
            {(p) => <Input {...p} type="date" max={today} value={date} onChange={(e) => setDate(e.target.value)} />}
          </Field>
          <Field label="Terms (days)" error={fields.termsDays}>
            {(p) => <Input {...p} inputMode="numeric" value={terms} onChange={(e) => setTerms(e.target.value.replace(/\D/g, ""))} />}
          </Field>
          <Field label="Delivery" optional error={fields.deliveryRef} hint="The receipt in Inventory.">
            {(p) => <Input {...p} value={deliveryRef} onChange={(e) => setDeliveryRef(e.target.value)} maxLength={60} />}
          </Field>
        </div>
      </section>

      <section className="space-y-3 rounded-[3px] border border-rule bg-sheet p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-semibold">What it&apos;s for</p>
          <label className="flex items-center gap-2 text-meta text-ink-2">
            <input type="checkbox" checked={includeVat} onChange={(e) => setIncludeVat(e.target.checked)} />
            The amounts include VAT, as on the supplier&apos;s invoice
          </label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[52rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                <th className="py-1.5 pr-2 font-semibold">Description</th>
                <th className="w-56 px-2 py-1.5 font-semibold">Account</th>
                <th className="w-44 px-2 py-1.5 font-semibold">VAT</th>
                <th className="w-32 px-2 py-1.5 text-right font-semibold">Amount</th>
                <th className="w-20 px-2 py-1.5 text-center font-semibold">Withhold</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody>
              {lines.map((l, i) => (
                <tr key={l.key} className="align-top">
                  <td className="py-1.5 pr-2">
                    <CellInput aria-label={`Line ${i + 1}: description`} aria-invalid={fields[`lines.${i}.description`] ? true : undefined} className="w-full !text-left" value={l.description} onChange={(e) => set(l.key, { description: e.target.value })} maxLength={200} placeholder="Gloves, 10 boxes" />
                  </td>
                  <td className="px-2 py-1.5">
                    <select aria-label={`Line ${i + 1}: account`} value={l.accountId} onChange={(e) => set(l.key, { accountId: e.target.value })} className="h-8 w-full rounded-[3px] border border-rule-strong bg-sheet px-1.5 text-sm">
                      {setup.accounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.code} {a.name}
                        </option>
                      ))}
                    </select>
                    {fields[`lines.${i}.accountId`] && <p className="mt-0.5 text-meta text-danger">{fields[`lines.${i}.accountId`]}</p>}
                  </td>
                  <td className="px-2 py-1.5">
                    <select aria-label={`Line ${i + 1}: VAT`} value={l.kind} onChange={(e) => set(l.key, { kind: e.target.value })} className="h-8 w-full rounded-[3px] border border-rule-strong bg-sheet px-1.5 text-sm">
                      {setup.kinds.filter((k) => !nonVat || k.key !== "vatable").map((k) => (
                        <option key={k.key} value={k.key}>
                          {k.label}
                        </option>
                      ))}
                    </select>
                    {fields[`lines.${i}.kind`] && <p className="mt-0.5 text-meta text-danger">{fields[`lines.${i}.kind`]}</p>}
                  </td>
                  <td className="px-2 py-1.5">
                    <CellInput aria-label={`Line ${i + 1}: amount`} aria-invalid={fields[`lines.${i}.amountCentavos`] ? true : undefined} inputMode="decimal" className="text-right" value={l.amount} onChange={(e) => set(l.key, { amount: e.target.value })} />
                  </td>
                  <td className="px-2 py-1.5 text-center">
                    <input type="checkbox" aria-label={`Line ${i + 1}: tax is withheld on it`} checked={l.withheld} disabled={!atc} onChange={(e) => set(l.key, { withheld: e.target.checked })} />
                  </td>
                  <td className="py-1.5">
                    {lines.length > 1 && (
                      <button type="button" aria-label={`Remove line ${i + 1}`} onClick={() => setLines(lines.filter((x) => x.key !== l.key))} className="grid size-8 place-items-center rounded-[3px] text-ink-3 hover:bg-bench hover:text-danger">
                        <Trash2 className="size-4" aria-hidden />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Button type="button" size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => setLines([...lines, blank(Date.now(), nonVat ? "non_vat" : "vatable")])}>
          Add line
        </Button>
      </section>

      <section className="grid gap-5 rounded-[3px] border border-rule bg-sheet p-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-4">
          <p className="text-sm font-semibold">Tax withheld from the supplier (expanded withholding)</p>
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_8rem]">
            <Field label="ATC" optional error={fields.atc} hint="As the BIR lists it. None: nothing is withheld.">
              {(p) => (
                <Select {...p} value={atc} onChange={(e) => pickAtc(e.target.value)}>
                  <option value="">None</option>
                  {setup.atcs.map((a) => (
                    <option key={a.code} value={a.code}>
                      {a.code}: {a.nature} ({a.rateBp / 100}%)
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Rate (%)" error={fields.ewtRateBp}>
              {(p) => <Input {...p} inputMode="decimal" value={rate} disabled={!atc} onChange={(e) => setRate(e.target.value)} />}
            </Field>
          </div>
          <Field label="Notes" optional error={fields.notes}>
            {(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500} />}
          </Field>
        </div>
        <dl className="space-y-1.5 self-start rounded-[3px] bg-bench/60 p-4 text-sm tabular-nums">
          <div className="flex justify-between"><dt className="text-ink-2">Net of VAT</dt><dd>{fmt.peso(preview.net)}</dd></div>
          <div className="flex justify-between"><dt className="text-ink-2">Input VAT</dt><dd>{fmt.peso(preview.vat)}</dd></div>
          <div className="flex justify-between font-semibold"><dt>Invoice total</dt><dd>{fmt.peso(preview.net + preview.vat)}</dd></div>
          <div className="flex justify-between"><dt className="text-ink-2">Tax withheld{atc ? ` (${atc})` : ""}</dt><dd>{ewt ? `− ${fmt.peso(ewt)}` : fmt.peso(0)}</dd></div>
          <div className="flex justify-between border-t border-ink pt-1.5 font-semibold"><dt>To pay the supplier</dt><dd>{fmt.peso(preview.net + preview.vat - ewt)}</dd></div>
        </dl>
      </section>

      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          Save draft
        </Button>
        <Button type="button" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
