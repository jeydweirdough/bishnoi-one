"use client";

import { Calculator, Plus, Trash2 } from "lucide-react";
import { useState, useTransition } from "react";
import { Button } from "@/src/platform/ui/button";
import { CellInput, Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { Flag } from "@/src/platform/ui/marks";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { computeSale } from "./actions";
import type { ComputedSale, TaxSetup } from "./types";

type Row = { description: string; quantity: string; price: string; discount: string; category: string; relief: boolean };

// A worked example to start from: one of each kind a pharmacy sells.
const EXAMPLE: Row[] = [
  { description: "Losartan 50mg (box of 30)", quantity: "1", price: "336.00", discount: "", category: "standard", relief: true },
  { description: "Metformin 500mg (VAT-exempt)", quantity: "2", price: "150.00", discount: "", category: "exempt", relief: true },
  { description: "Face masks (box of 50)", quantity: "1", price: "224.00", discount: "", category: "standard", relief: false },
];

/**
 * Work a sale out exactly as the engine will on an invoice: the lines, who is
 * buying, and the Sales Invoice summary it comes to. Nothing is saved.
 */
export function SaleTryout({ setup, org }: { setup: TaxSetup; org: Org }) {
  const fmt = makeFormat(org);
  const [pending, start] = useTransition();
  const [rows, setRows] = useState<Row[]>(EXAMPLE);
  const [treatment, setTreatment] = useState("regular");
  const [idNumber, setIdNumber] = useState("");
  const [buyerName, setBuyerName] = useState("");
  const [on, setOn] = useState(setup.today);
  const [result, setResult] = useState<ComputedSale | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const needsId = setup.pack.treatments.find((t) => t.key === treatment)?.needsId ?? false;
  const setRow = (n: number, change: Partial<Row>) => setRows(rows.map((r, i) => (i === n ? { ...r, ...change } : r)));

  function run() {
    const lines = rows.map((r) => ({
      description: r.description.trim() || null,
      quantity: Number.parseInt(r.quantity, 10) || 0,
      unitPriceCentavos: fmt.toCentavos(r.price || "0") ?? -1,
      discountCentavos: r.discount ? (fmt.toCentavos(r.discount) ?? -1) : 0,
      category: r.category,
      reliefEligible: r.relief,
    }));
    if (lines.some((l) => l.unitPriceCentavos < 0 || l.discountCentavos < 0)) return setError("Enter amounts like 112.00.");
    start(async () => {
      const r = await computeSale({
        treatment,
        on: on || null,
        pricesIncludeTax: null,
        buyer: { name: buyerName.trim() || null, tin: null, address: null, idNumber: idNumber.trim() || null },
        lines,
      });
      if (r.ok) {
        setResult(r.data);
        setError(null);
        setFields({});
        return;
      }
      setResult(null);
      setError(r.error);
      setFields(r.fields ?? {});
    });
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          run();
        }}
        className="space-y-5"
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[44rem] text-left text-sm">
            <thead>
              <tr className="border-b border-rule text-caps text-ink-3 uppercase">
                <th scope="col" className="py-2 pr-2 font-semibold">Item</th>
                <th scope="col" className="px-2 py-2 text-right font-semibold">Qty</th>
                <th scope="col" className="px-2 py-2 text-right font-semibold">Price ({fmt.symbol})</th>
                <th scope="col" className="px-2 py-2 font-semibold">VAT</th>
                <th scope="col" className="px-2 py-2 font-semibold whitespace-nowrap" title="Covered by the senior citizen and PWD 20% (medicines, for one)">SC/PWD</th>
                <th scope="col" className="py-2 pl-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {rows.map((r, n) => (
                <tr key={n}>
                  <td className="py-2 pr-2">
                    <CellInput className="w-full !text-left" aria-label={`Line ${n + 1}: item`} value={r.description} onChange={(e) => setRow(n, { description: e.target.value })} />
                  </td>
                  <td className="px-2 py-2 text-right">
                    <CellInput className="w-14" inputMode="numeric" aria-label={`Line ${n + 1}: quantity`} value={r.quantity} onChange={(e) => setRow(n, { quantity: e.target.value.replace(/\D/g, "") })} />
                  </td>
                  <td className="px-2 py-2 text-right">
                    <CellInput className="w-24" inputMode="decimal" aria-label={`Line ${n + 1}: unit price`} value={r.price} onChange={(e) => setRow(n, { price: e.target.value })} />
                  </td>
                  <td className="px-2 py-2">
                    <select
                      aria-label={`Line ${n + 1}: VAT category`}
                      value={r.category}
                      onChange={(e) => setRow(n, { category: e.target.value })}
                      className="h-8 rounded-[3px] border border-rule-strong bg-sheet px-1.5 text-meta"
                    >
                      {setup.pack.categories.map((c) => (
                        <option key={c.key} value={c.key}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-2 py-2 text-center">
                    <input type="checkbox" aria-label={`Line ${n + 1}: covered by the SC/PWD discount`} checked={r.relief} onChange={(e) => setRow(n, { relief: e.target.checked })} className="size-4 accent-hema" />
                  </td>
                  <td className="py-2 pl-2 text-right">
                    <Button size="sm" variant="quiet" disabled={rows.length === 1} onClick={() => setRows(rows.filter((_, i) => i !== n))} aria-label={`Remove line ${n + 1}`} title="Remove this line" icon={<Trash2 className="size-4" aria-hidden />} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Button size="sm" onClick={() => setRows([...rows, { description: "", quantity: "1", price: "", discount: "", category: "standard", relief: false }])} icon={<Plus className="size-4" aria-hidden />}>
          Add a line
        </Button>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Buyer" error={fields.treatment}>
            {(f) => (
              <Select {...f} value={treatment} onChange={(e) => setTreatment(e.target.value)}>
                {setup.pack.treatments.map((t) => (
                  <option key={t.key} value={t.key}>
                    {t.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Date of the sale" error={fields.on} hint="Rates are the ones in force that day.">
            {(f) => <Input {...f} type="date" value={on} onChange={(e) => setOn(e.target.value)} />}
          </Field>
          {needsId && (
            <>
              <Field label="Their name" optional>
                {(f) => <Input {...f} value={buyerName} onChange={(e) => setBuyerName(e.target.value)} />}
              </Field>
              <Field label="OSCA or PWD ID number" error={fields.idNumber}>
                {(f) => <Input {...f} value={idNumber} onChange={(e) => setIdNumber(e.target.value)} />}
              </Field>
            </>
          )}
        </div>
        <FormError message={error} />
        <Button type="submit" variant="primary" loading={pending} icon={<Calculator className="size-4" aria-hidden />}>
          Work it out
        </Button>
      </form>

      <InvoiceSummary result={result} fmt={fmt} />
    </div>
  );
}

function InvoiceSummary({ result, fmt }: { result: ComputedSale | null; fmt: ReturnType<typeof makeFormat> }) {
  if (!result) {
    return (
      <div className="grid min-h-48 place-content-center rounded-[3px] border-2 border-dashed border-rule p-6 text-center text-meta text-ink-3">
        The Sales Invoice summary shows here.
      </div>
    );
  }
  return (
    <section aria-label="Sales Invoice summary" className="h-fit rounded-[3px] border border-ink bg-sheet p-5 text-sm">
      <header className="border-b-[3px] border-double border-ink pb-3 text-center">
        <p className="font-semibold">{result.seller.registeredName ?? "(registered name)"}</p>
        {result.seller.tradeName && <p className="text-meta">{result.seller.tradeName}</p>}
        <p className="text-meta text-ink-2">{result.seller.address ?? "(registered address)"}</p>
        <p className="text-meta text-ink-2">
          {result.seller.regime === "vat" ? "VAT Reg." : "Non-VAT Reg."} TIN: {result.seller.tin ?? "(TIN)"}
        </p>
        <p className="mt-2 text-stamp tracking-[0.12em] uppercase">{result.document}</p>
      </header>
      {result.warnings.map((w) => (
        <p key={w} className="mt-3">
          <Flag letter="!">{w}</Flag>
        </p>
      ))}
      <ul className="mt-3 divide-y divide-rule">
        {result.lines.map((l, n) => (
          <li key={n} className="flex justify-between gap-3 py-1.5">
            <span className="min-w-0">
              {l.description ?? `Line ${n + 1}`}
              <span className="block text-meta text-ink-3">
                {l.codeName}
                {l.reliefCentavos > 0 ? ` · less ${fmt.peso(l.reliefCentavos)}` : ""}
              </span>
            </span>
            <span className="shrink-0 tabular-nums">{fmt.peso(l.totalCentavos)}</span>
          </li>
        ))}
      </ul>
      <dl className="mt-3 space-y-1 border-t border-ink pt-3">
        {result.summary.map((s) => (
          <div key={s.key} className="flex justify-between">
            <dt className="text-ink-2">{s.label}</dt>
            <dd className="tabular-nums">{fmt.peso(s.amountCentavos)}</dd>
          </div>
        ))}
        <div className="flex justify-between border-t border-rule pt-2 font-semibold">
          <dt>Total Amount Due</dt>
          <dd className="tabular-nums">{fmt.peso(result.totalDueCentavos)}</dd>
        </div>
      </dl>
      {/* The sales above are already after the discount; it's stated, not subtracted again. */}
      {result.relief && (
        <p className="mt-2 flex justify-between gap-3 text-meta text-ink-2">
          <span>{result.relief.label}, already taken off above</span>
          <span className="tabular-nums">{fmt.peso(result.relief.amountCentavos)}</span>
        </p>
      )}
      {(result.buyer.name || result.buyer.idNumber) && (
        <p className="mt-3 text-meta text-ink-2">
          {result.treatment.name}: {result.buyer.name ?? "(name)"} · ID {result.buyer.idNumber}
        </p>
      )}
      {result.notice && <p className="mt-3 text-center text-meta font-semibold">{result.notice}</p>}
      {result.sellerTax && (
        <p className="mt-3 border-t border-rule pt-2 text-meta text-ink-3">
          Not on the invoice: {result.sellerTax.name} of {fmt.peso(result.sellerTax.amountCentavos)} ({result.sellerTax.rateBp / 100}%) is the company&apos;s to pay on this sale.
        </p>
      )}
    </section>
  );
}
