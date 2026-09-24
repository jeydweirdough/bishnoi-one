"use client";

import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { counterSale } from "../actions/pharmacy";
import { PAYMENT_METHODS } from "../lib/words";
import type { PaymentMethod } from "../lib/types";

type Option = { id: string; label: string; unit: string; priceCentavos: number; available: number };
type Line = { medicineId: string; quantity: string };

/**
 * A counter sale: over-the-counter medicines only, taken from whichever
 * batches expire soonest. Prescription medicines aren't offered here: they
 * go out through a verified prescription and Dispensing.
 */
export function SaleForm({ medicines, customers, org }: { medicines: Option[]; customers: { id: string; fullName: string }[]; org: Org }) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const [pending, start] = useTransition();
  const [lines, setLines] = useState<Line[]>([{ medicineId: "", quantity: "1" }]);
  const [customer, setCustomer] = useState("");
  const [payment, setPayment] = useState<PaymentMethod>("cash");
  const [discount, setDiscount] = useState("");
  const [error, setError] = useState<string | null>(null);
  const setLine = (n: number, change: Partial<Line>) => setLines(lines.map((l, i) => (i === n ? { ...l, ...change } : l)));

  const priced = lines.map((l) => {
    const m = medicines.find((x) => x.id === l.medicineId);
    const qty = Number.parseInt(l.quantity, 10) || 0;
    return { m, qty, total: m ? m.priceCentavos * qty : 0 };
  });
  const subtotal = priced.reduce((s, p) => s + p.total, 0);
  const discountCentavos = discount ? (fmt.toCentavos(discount) ?? -1) : 0;

  function submit() {
    if (discountCentavos < 0) return setError("Enter the discount as an amount, like 25.00.");
    start(async () => {
      const result = await counterSale({
        patientId: customer || null,
        lines: lines.filter((l) => l.medicineId).map((l) => ({ medicineId: l.medicineId, quantity: Number.parseInt(l.quantity, 10) || 0 })),
        paymentMethod: payment,
        discountCentavos,
        notes: null,
      });
      if (result.ok) {
        toast.success("Sale recorded", { description: `${result.data.number} · ${fmt.peso(result.data.totalCentavos)}` });
        router.push(`/sales/${result.data.id}`);
        router.refresh();
        return;
      }
      setError(result.error);
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-6"
    >
      <div className="space-y-3">
        {lines.map((l, n) => {
          const p = priced[n];
          return (
            <div key={n} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_7rem_7rem_auto] sm:items-end">
              <Field label="Medicine" hint={p.m ? `${p.m.available} ${p.m.unit}(s) available · ${fmt.peso(p.m.priceCentavos)} each` : undefined}>
                {(fp) => (
                  <Select {...fp} value={l.medicineId} onChange={(e) => setLine(n, { medicineId: e.target.value })}>
                    <option value="">Pick an OTC medicine</option>
                    {medicines.map((m) => (
                      <option key={m.id} value={m.id} disabled={m.available === 0}>
                        {m.label}
                        {m.available === 0 ? " (out of stock)" : ""}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="Quantity">
                {(fp) => <Input {...fp} inputMode="numeric" value={l.quantity} onChange={(e) => setLine(n, { quantity: e.target.value.replace(/\D/g, "") })} />}
              </Field>
              <p className="pb-2 text-right text-sm tabular-nums">{fmt.peso(p.total)}</p>
              <Button
                size="sm"
                variant="quiet"
                disabled={lines.length === 1}
                onClick={() => setLines(lines.filter((_, i) => i !== n))}
                aria-label={`Remove line ${n + 1}`}
                title="Remove this line"
                icon={<Trash2 className="size-4" aria-hidden />}
              />
            </div>
          );
        })}
        <Button size="sm" onClick={() => setLines([...lines, { medicineId: "", quantity: "1" }])} icon={<Plus className="size-4" aria-hidden />}>
          Add a line
        </Button>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Customer" optional hint="For their purchase history. Leave empty for a walk-in.">
          {(p) => (
            <Select {...p} value={customer} onChange={(e) => setCustomer(e.target.value)}>
              <option value="">Walk-in</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.fullName}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={`Discount (${fmt.symbol})`} optional>
          {(p) => <Input {...p} inputMode="decimal" value={discount} onChange={(e) => setDiscount(e.target.value)} placeholder="0.00" />}
        </Field>
        <div className="sm:col-span-2">
          <Choice
            name="payment"
            legend="Paid by"
            value={payment}
            onChange={setPayment}
            options={(Object.keys(PAYMENT_METHODS) as PaymentMethod[]).map((m) => ({ value: m, label: PAYMENT_METHODS[m] }))}
          />
        </div>
      </div>

      <FormError message={error} />
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-4">
        <p className="text-sm">
          Total <span className="font-semibold">{fmt.peso(Math.max(0, subtotal - Math.max(0, discountCentavos)))}</span>
        </p>
        <div className="flex gap-2">
          <LinkButton href="/sales" variant="quiet">
            Cancel
          </LinkButton>
          <Button type="submit" variant="primary" loading={pending} disabled={subtotal === 0}>
            Record sale
          </Button>
        </div>
      </div>
    </form>
  );
}
