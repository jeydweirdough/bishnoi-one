"use client";

import { Plus, Search, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { CellInput, Field, FormError, FormGrid, Input, Select, Textarea } from "@/src/modules/finance/platform/ui/field";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { formatTin } from "@/src/modules/finance/lib/tin";
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
    tin: formatTin(invoice?.customer.tin ?? ""),
    address: invoice?.customer.address ?? "",
  });
  // Whose sale it is (the CRM scores it): the CRM customer's owner.
  const [salesperson, setSalesperson] = useState(invoice?.salesperson ?? null);
  // Their division and team (revenue by division), as the CRM gives them with the owner.
  const [unit, setUnit] = useState({ division: invoice?.division ?? null, team: invoice?.team ?? null });
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
  // A saved draft the tax step can't work out yet says why, beside the field (2026-10-22).
  const [fields, setFields] = useState<Record<string, string>>(invoice?.problemFields ?? {});
  const [error, setError] = useState<string | null>(invoice?.problem ?? null);
  const [pending, start] = useTransition();
  const set = (key: number, patch: Partial<Line>) => setLines(lines.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  const needsId = choices.treatments.find((t) => t.key === treatment)?.needsId ?? false;

  // Finding the customer in the CRM.
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Customer[] | null>(null);
  const [crmProblem, setCrmProblem] = useState<string | null>(null);
  const [searching, search] = useTransition();
  function lookUp() {
    if (!q.trim()) return;
    search(async () => {
      const result = await findCustomers(q.trim());
      if (!result.ok) {
        // Said beside the box, not only in a toast that goes away.
        setCrmProblem(result.error);
        setFound(null);
        return;
      }
      setCrmProblem(null);
      setFound(result.data);
    });
  }
  function pick(c: Customer) {
    setCustomer({ id: c.id, name: c.name, tin: c.tin ?? "", address: c.address ?? "" });
    setSalesperson(c.owner ?? null);
    setUnit({ division: c.owner?.division ?? null, team: c.owner?.team ?? null });
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
        divisionId: unit.division?.id ?? null,
        divisionName: unit.division?.name ?? null,
        teamId: unit.team?.id ?? null,
        teamName: unit.team?.name ?? null,
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
      if (result.data.problem) {
        // Saved, but it can't be issued yet: stay on the draft, with what's wrong beside the field.
        toast.warning("Draft saved, but it needs fixing before it can be issued", { description: result.data.problem, duration: 10000 });
        setFields(result.data.problemFields ?? {});
        setError(result.data.problem);
        router.push(`/finance/invoices/${result.data.id}?edit=1`);
        return;
      }
      toast.success("Draft saved");
      router.push(`/finance/invoices/${result.data.id}`);
    });
  }

  // Studio Admin's Invoice (2026-11-19): the form on the left, the paper as it will read on the right.
  return (
    <div className="grid items-start gap-5 2xl:grid-cols-2">
    <form onSubmit={submit} noValidate className="min-w-0 space-y-5">
      <section className="space-y-4 rounded-xl bg-card text-card-foreground ring-1 ring-foreground/10 p-5">
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
            {/* It only searches: what's typed here isn't kept (asked 2026-10-22, when it seemed to vanish on saving). */}
            {crmProblem ? (
              <p className="mt-1 text-meta text-danger">{crmProblem} Type the customer&apos;s details below instead.</p>
            ) : (
              !found &&
              !customer.id && (
                <p className="mt-1 text-meta text-ink-3">
                  Searches the CRM&apos;s customers so you can pick one; what you type here isn&apos;t saved. The invoice&apos;s customer is the details below.
                </p>
              )
            )}
            {found && (
              <ul className="mt-2 divide-y divide-rule rounded-lg border border-rule">
                {found.length === 0 && <li className="px-3 py-2 text-meta text-ink-3">No customer matches. Type their details below.</li>}
                {found.map((c) => (
                  <li key={c.id}>
                    <button suppressHydrationWarning type="button" onClick={() => pick(c)} className="w-full px-3 py-2 text-left text-sm hover:bg-hema-tint">
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
                {salesperson?.name && (unit.team ?? unit.division) && <> · {[unit.division?.name, unit.team?.name].filter(Boolean).join(" › ")}</>}
                {!salesperson?.name && " (assign the customer to someone in the CRM, or this sale counts for nobody)"}
              </p>
            )}
          </div>
        )}
        <FormGrid>
          <Field label="Customer" size="lg" error={fields.customerName}>
            {(p) => <Input {...p} value={customer.name} onChange={(e) => setCustomer({ ...customer, name: e.target.value })} maxLength={200} />}
          </Field>
          <Field label="TIN" size="sm" optional error={fields.customerTin} hint="Type the digits only: the dashes go in by themselves. 9 digits, then the branch code if any. Required when the customer is VAT-registered.">
            {(p) => (
              <Input
                {...p}
                inputMode="numeric"
                value={customer.tin}
                onChange={(e) => setCustomer({ ...customer, tin: formatTin(e.target.value) })}
                placeholder="123-456-789-00000"
                maxLength={17}
              />
            )}
          </Field>
          <Field label="Address" optional error={fields.customerAddress} size="full">
            {(p) => <Input {...p} value={customer.address} onChange={(e) => setCustomer({ ...customer, address: e.target.value })} maxLength={300} />}
          </Field>
          <Field label="Buyer type" size="md" error={fields.treatment}>
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
            <Field label="ID number" size="md" error={fields.buyerIdNumber} hint="The senior citizen's OSCA ID or the PWD ID.">
              {(p) => <Input {...p} value={idNumber} onChange={(e) => setIdNumber(e.target.value)} maxLength={40} />}
            </Field>
          )}
        </FormGrid>
      </section>

      <section className="space-y-3 rounded-xl bg-card text-card-foreground ring-1 ring-foreground/10 p-5">
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
                    <CellInput aria-label={`Line ${i + 1}: description`} className="text-left" value={l.description} onChange={(e) => set(l.key, { description: e.target.value })} maxLength={200} placeholder="Amoxicillin 500 mg, box of 100" />
                    {needsId && (
                      <label className="mt-1 flex items-center gap-1.5 text-meta text-ink-2">
                        <input suppressHydrationWarning type="checkbox" checked={l.relief} onChange={(e) => set(l.key, { relief: e.target.checked })} />
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
                    <Select aria-label={`Line ${i + 1}: VAT category`} value={l.category} onChange={(e) => set(l.key, { category: e.target.value })}>
                      {choices.categories.map((c) => (
                        <option key={c.key} value={c.key}>
                          {c.name}
                        </option>
                      ))}
                    </Select>
                  </td>
                  <td className="py-1.5 pl-1">
                    {lines.length > 1 && (
                      <button suppressHydrationWarning type="button" aria-label={`Remove line ${i + 1}`} onClick={() => setLines(lines.filter((x) => x.key !== l.key))} className="inline-flex size-8 items-center justify-center rounded-lg text-ink-3 hover:bg-danger/10 hover:text-danger">
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

      <section className="grid gap-4 rounded-xl bg-card text-card-foreground ring-1 ring-foreground/10 p-5 sm:grid-cols-3">
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
    <InvoicePaper org={org} customer={customer} lines={lines} date={date} terms={terms} reference={reference} notes={notes} fmt={fmt} />
    </div>
  );
}

/** The invoice as it will read, kept in step with the form (amounts before VAT is worked out on saving). */
function InvoicePaper({ org, customer, lines, date, terms, reference, notes, fmt }: {
  org: Org;
  customer: { name: string; tin: string; address: string };
  lines: Line[];
  date: string;
  terms: string;
  reference: string;
  notes: string;
  fmt: ReturnType<typeof makeFormat>;
}) {
  const rows = lines.map((l) => {
    const qty = Number(l.quantity) || 0;
    const price = fmt.toCentavos(l.price) ?? 0;
    const discount = fmt.toCentavos(l.discount) ?? 0;
    return { key: l.key, description: l.description, qty, price, amount: Math.max(0, Math.round(qty * price) - discount) };
  });
  const total = rows.reduce((n, r) => n + r.amount, 0);
  return (
    <aside className="sticky top-16 hidden rounded-xl bg-card p-8 text-sm ring-1 ring-foreground/10 2xl:block print:hidden" aria-label="Preview">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xl font-medium tracking-tight">Sales invoice</p>
          <p className="text-muted-foreground">{org.brandName || org.name}</p>
        </div>
        <div className="text-right text-muted-foreground">
          <p>{date ? fmt.dateLabel(date) : "No date"}</p>
          <p>{terms ? `Due in ${terms} days` : ""}</p>
          {reference && <p>Ref. {reference}</p>}
        </div>
      </div>
      <div className="mt-8">
        <p className="text-xs text-muted-foreground">Bill to</p>
        <p className="font-medium">{customer.name || "Customer"}</p>
        {customer.address && <p className="text-muted-foreground">{customer.address}</p>}
        {customer.tin && <p className="text-muted-foreground">TIN {customer.tin}</p>}
      </div>
      <table className="mt-8 w-full">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th className="py-2 font-normal">Description</th>
            <th className="py-2 text-right font-normal">Qty</th>
            <th className="py-2 text-right font-normal">Price</th>
            <th className="py-2 text-right font-normal">Amount</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-b">
              <td className="py-2 pr-2">{r.description || <span className="text-muted-foreground">Item</span>}</td>
              <td className="py-2 text-right tabular-nums">{r.qty}</td>
              <td className="py-2 text-right tabular-nums">{fmt.peso(r.price)}</td>
              <td className="py-2 text-right tabular-nums">{fmt.peso(r.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-4 ml-auto w-64 space-y-1">
        <div className="flex justify-between text-base font-medium">
          <span>Total</span>
          <span className="tabular-nums">{fmt.peso(total)}</span>
        </div>
        <p className="text-xs text-muted-foreground">VAT is worked out when the draft is saved.</p>
      </div>
      {notes && <p className="mt-8 border-t pt-4 whitespace-pre-wrap text-muted-foreground">{notes}</p>}
    </aside>
  );
}
