"use client";

import { Plus, Search, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { CellInput, Field, FormError, Input, Select, Textarea } from "@/src/modules/finance/platform/ui/field";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { findCustomers, saveInvoice } from "@/src/modules/finance/invoices/actions";
import type { Customer, Invoice, TaxChoices } from "@/src/modules/finance/invoices/types";

type Line = { key: number; description: string; ref: string; quantity: string; price: string; discount: string; category: string; relief: boolean };
const blank = (key: number): Line => ({ key, description: "", ref: "", quantity: "1", price: "", discount: "", category: "standard", relief: false });

/**
 * A draft invoice: who it's billed to, what they bought, and the terms. The
 * amounts and tax are worked out by the API when it's saved, and shown on the
 * invoice's page, where it's issued.
 */
export function InvoiceEditor({ invoice, choices, org, today, crmLinked }: { invoice: Invoice | null; choices: TaxChoices; org: Org; today: string; crmLinked: boolean }) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const money = (minor: number) => (minor ? String(minor / 10 ** (org.minorUnits ?? 2)) : "");
  const [customer, setCustomer] = useState({
    id: invoice?.customer.id ?? null,
    name: invoice?.customer.name ?? "",
    tin: invoice?.customer.tin ?? "",
    address: invoice?.customer.address ?? "",
  });
  // Whose sale it is (the CRM scores it): the CRM customer's owner.
  const [salesperson, setSalesperson] = useState(invoice?.salesperson ?? null);
  const [treatment, setTreatment] = useState(invoice?.treatment ?? "regular");
  const [idNumber, setIdNumber] = useState(invoice?.buyerIdNumber ?? "");
  const [date, setDate] = useState(invoice?.date ?? today);
  const [terms, setTerms] = useState(String(invoice?.termsDays ?? 30));
  const [reference, setReference] = useState(invoice?.reference ?? "");
  const [notes, setNotes] = useState(invoice?.notes ?? "");
  const [lines, setLines] = useState<Line[]>(
    invoice?.lines.length
      ? invoice.lines.map((l, i) => ({
          key: i,
          description: l.description ?? "",
          ref: l.ref ?? "",
          quantity: String(l.quantity),
          price: money(l.unitPriceCentavos),
          discount: money(l.discountCentavos),
          category: l.category,
          relief: l.reliefEligible,
        }))
      : [blank(0)],
  );
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const set = (key: number, patch: Partial<Line>) => setLines(lines.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  const needsId = choices.treatments.find((t) => t.key === treatment)?.needsId ?? false;

  // Finding the customer in the CRM.
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Customer[] | null>(null);
  const [searching, search] = useTransition();
  function lookUp() {
    if (!q.trim()) return;
    search(async () => {
      const result = await findCustomers(q.trim());
      if (!result.ok) {
        toast.error(result.error);
        setFound(null);
        return;
      }
      setFound(result.data);
    });
  }
  function pick(c: Customer) {
    setCustomer({ id: c.id, name: c.name, tin: c.tin ?? "", address: c.address ?? "" });
    setSalesperson(c.owner ?? null);
    setFound(null);
    setQ("");
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const used = lines.filter((l) => l.description.trim() || l.price.trim());
    const problems: Record<string, string> = {};
    if (!customer.name.trim()) problems.customerName = "Enter the customer name.";
    if (!used.length) problems.lines = "Add at least one line.";
    used.forEach((l, i) => {
      if (!(Number(l.quantity) >= 1)) problems[`lines.${i}.quantity`] = "At least 1.";
      if (fmt.toCentavos(l.price) === null) problems[`lines.${i}.unitPriceCentavos`] = "Enter a price.";
    });
    if (needsId && !idNumber.trim()) problems.buyerIdNumber = "Enter the buyer's ID number.";
    if (Object.keys(problems).length) {
      setFields(problems);
      setError(problems.lines ?? "Please review the highlighted fields.");
      return;
    }
    start(async () => {
      const result = await saveInvoice(invoice?.id ?? null, {
        customerId: customer.id,
        customerName: customer.name.trim(),
        customerTin: customer.tin.trim() || null,
        customerAddress: customer.address.trim() || null,
        salespersonId: salesperson?.id ?? null,
        salespersonName: salesperson?.name ?? null,
        treatment,
        buyerIdNumber: idNumber.trim() || null,
        invoiceDate: date,
        termsDays: Number(terms) || 0,
        reference: reference.trim() || null,
        notes: notes.trim() || null,
        pricesIncludeTax: null,
        lines: used.map((l) => ({
          description: l.description.trim() || null,
          ref: l.ref.trim() || null,
          quantity: Math.round(Number(l.quantity)),
          unitPriceCentavos: fmt.toCentavos(l.price) ?? 0,
          discountCentavos: fmt.toCentavos(l.discount) ?? 0,
          category: l.category,
          reliefEligible: l.relief,
        })),
      });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success("Draft saved");
      router.push(`/finance/invoices/${result.data.id}`);
    });
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <section className="space-y-4 rounded-[3px] border border-rule bg-sheet p-5">
        <p className="text-sm font-semibold">Bill to</p>
        {crmLinked && (
          <div>
            <div className="flex gap-2">
              <Input
                aria-label="Find a customer in the CRM"
                placeholder="Find a customer in the CRM: name, email or phone"
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
            {found && (
              <ul className="mt-2 divide-y divide-rule rounded-[3px] border border-rule">
                {found.length === 0 && <li className="px-3 py-2 text-meta text-ink-3">No customer matches. Type their details below.</li>}
                {found.map((c) => (
                  <li key={c.id}>
                    <button type="button" onClick={() => pick(c)} className="w-full px-3 py-2 text-left text-sm hover:bg-hema-tint">
                      <span className="font-semibold">{c.name}</span>
                      {c.address && <span className="text-ink-3"> · {c.address}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {customer.id && <p className="mt-1 text-meta text-ink-3">From the CRM. Changing the details below changes this invoice only.</p>}
            {customer.id && (
              <p className="mt-1 text-meta text-ink-2">
                Salesperson: <span className="font-medium text-ink">{salesperson?.name ?? "None"}</span>
                {!salesperson?.name && " (assign the customer to someone in the CRM, or this sale counts for nobody)"}
              </p>
            )}
          </div>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Customer" error={fields.customerName}>
            {(p) => <Input {...p} value={customer.name} onChange={(e) => setCustomer({ ...customer, name: e.target.value })} maxLength={200} />}
          </Field>
          <Field label="TIN" optional error={fields.customerTin} hint="Required on the invoice when the customer is VAT-registered.">
            {(p) => <Input {...p} value={customer.tin} onChange={(e) => setCustomer({ ...customer, tin: e.target.value })} placeholder="123-456-789-00000" maxLength={20} />}
          </Field>
          <Field label="Address" optional error={fields.customerAddress} className="sm:col-span-2">
            {(p) => <Input {...p} value={customer.address} onChange={(e) => setCustomer({ ...customer, address: e.target.value })} maxLength={300} />}
          </Field>
          <Field label="Buyer type" error={fields.treatment}>
            {(p) => (
              <Select {...p} value={treatment} onChange={(e) => setTreatment(e.target.value)}>
                {choices.treatments.map((t) => (
                  <option key={t.key} value={t.key}>
                    {t.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {needsId && (
            <Field label="ID number" error={fields.buyerIdNumber} hint="The senior citizen's OSCA ID or the PWD ID.">
              {(p) => <Input {...p} value={idNumber} onChange={(e) => setIdNumber(e.target.value)} maxLength={40} />}
            </Field>
          )}
        </div>
      </section>

      <section className="space-y-3 rounded-[3px] border border-rule bg-sheet p-5">
        <p className="text-sm font-semibold">
          Items <span className="font-normal text-ink-3">· prices {choices.pricesIncludeTax ? "include" : "exclude"} VAT (Tax, Registration)</span>
        </p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[46rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                <th className="py-1.5 pr-2 font-semibold">Description</th>
                <th className="w-20 px-2 py-1.5 text-right font-semibold">Qty</th>
                <th className="w-32 px-2 py-1.5 text-right font-semibold">Unit price</th>
                <th className="w-28 px-2 py-1.5 text-right font-semibold">Discount</th>
                <th className="w-40 px-2 py-1.5 font-semibold">VAT</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody>
              {lines.map((l, i) => (
                <tr key={l.key} className="align-top">
                  <td className="py-1.5 pr-2">
                    <CellInput aria-label={`Line ${i + 1}: description`} value={l.description} onChange={(e) => set(l.key, { description: e.target.value })} maxLength={200} placeholder="Amoxicillin 500 mg, box of 100" />
                    {needsId && (
                      <label className="mt-1 flex items-center gap-1.5 text-meta text-ink-2">
                        <input type="checkbox" checked={l.relief} onChange={(e) => set(l.key, { relief: e.target.checked })} />
                        The 20% discount applies (medicines, for one)
                      </label>
                    )}
                  </td>
                  <td className="px-2 py-1.5">
                    <CellInput
                      aria-label={`Line ${i + 1}: quantity`}
                      aria-invalid={fields[`lines.${i}.quantity`] ? true : undefined}
                      inputMode="numeric"
                      className="text-right"
                      value={l.quantity}
                      onChange={(e) => set(l.key, { quantity: e.target.value })}
                    />
                  </td>
                  <td className="px-2 py-1.5">
                    <CellInput
                      aria-label={`Line ${i + 1}: unit price`}
                      aria-invalid={fields[`lines.${i}.unitPriceCentavos`] ? true : undefined}
                      inputMode="decimal"
                      className="text-right"
                      value={l.price}
                      onChange={(e) => set(l.key, { price: e.target.value })}
                      placeholder="0.00"
                    />
                  </td>
                  <td className="px-2 py-1.5">
                    <CellInput aria-label={`Line ${i + 1}: discount`} inputMode="decimal" className="text-right" value={l.discount} onChange={(e) => set(l.key, { discount: e.target.value })} placeholder="0.00" />
                  </td>
                  <td className="px-2 py-1.5">
                    <select
                      aria-label={`Line ${i + 1}: VAT category`}
                      value={l.category}
                      onChange={(e) => set(l.key, { category: e.target.value })}
                      className="h-8 w-full rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm"
                    >
                      {choices.categories.map((c) => (
                        <option key={c.key} value={c.key}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="py-1.5 pl-1">
                    {lines.length > 1 && (
                      <button type="button" aria-label={`Remove line ${i + 1}`} onClick={() => setLines(lines.filter((x) => x.key !== l.key))} className="inline-flex size-8 items-center justify-center rounded-[3px] text-ink-3 hover:bg-danger/10 hover:text-danger">
                        <Trash2 className="size-4" aria-hidden />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Button type="button" size="sm" icon={<Plus className="size-4" aria-hidden />} onClick={() => setLines([...lines, blank(Math.max(...lines.map((l) => l.key)) + 1)])}>
          Add a line
        </Button>
      </section>

      <section className="grid gap-4 rounded-[3px] border border-rule bg-sheet p-5 sm:grid-cols-3">
        <Field label="Invoice date" error={fields.invoiceDate}>
          {(p) => <Input {...p} type="date" max={today} value={date} onChange={(e) => setDate(e.target.value)} />}
        </Field>
        <Field label="Payment terms (days)" error={fields.termsDays} hint="0 for cash on delivery.">
          {(p) => <Input {...p} inputMode="numeric" value={terms} onChange={(e) => setTerms(e.target.value)} />}
        </Field>
        <Field label="Reference" optional error={fields.reference} hint="The customer's PO number, or the order.">
          {(p) => <Input {...p} value={reference} onChange={(e) => setReference(e.target.value)} maxLength={80} />}
        </Field>
        <Field label="Notes" optional error={fields.notes} className="sm:col-span-3">
          {(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500} />}
        </Field>
      </section>

      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {invoice ? "Save draft" : "Save as draft"}
        </Button>
        <Button type="button" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
