"use client";

import { Pill } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/modules/pharmacy/platform/ui/button";
import { CellInput, Choice, Field, FormError, FormGrid, Input, Textarea } from "@/src/modules/pharmacy/platform/ui/field";
import { Flag } from "@/src/modules/pharmacy/platform/ui/marks";
import { makeFormat } from "@/src/modules/pharmacy/platform/lib/format";
import type { Org } from "@/src/modules/pharmacy/platform/lib/types";
import { dispense } from "@/src/modules/pharmacy/actions/pharmacy";
import { PAYMENT_METHODS } from "@/src/modules/pharmacy/lib/words";
import type { PaymentMethod, Prepared } from "@/src/modules/pharmacy/lib/types";

/** First expiry, first out: fill what's owed from the soonest-expiring batch onward. */
function fefo(rx: Prepared): Record<string, string> {
  const out: Record<string, string> = {};
  for (const item of rx.items) {
    let left = item.remaining;
    for (const b of item.batches) {
      const n = Math.min(left, b.qtyOnHand);
      out[`${item.id}:${b.id}`] = n > 0 ? String(n) : "";
      left -= n;
    }
  }
  return out;
}

/**
 * Dispensing a verified prescription. For each medicine the pharmacist picks
 * how many come from which eligible batch; the soonest-expiring ones are
 * filled in first. Less than is owed is fine: the rest stays in the queue as
 * partly dispensed.
 */
export function DispenseForm({ rx, org }: { rx: Prepared; org: Org }) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const [pending, start] = useTransition();
  const [picked, setPicked] = useState<Record<string, string>>(() => fefo(rx));
  const [payment, setPayment] = useState<PaymentMethod>("cash");
  const [discount, setDiscount] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const qty = (key: string) => Number.parseInt(picked[key] || "0", 10) || 0;
  const perItem = rx.items.map((item) => ({
    item,
    total: item.batches.reduce((sum, b) => sum + qty(`${item.id}:${b.id}`), 0),
  }));
  const subtotal = perItem.reduce((sum, { item, total }) => sum + total * item.medicine.priceCentavos, 0);
  const discountCentavos = discount ? (fmt.toCentavos(discount) ?? -1) : 0;
  const units = perItem.reduce((s, p) => s + p.total, 0);
  const over = perItem.filter(({ item, total }) => total > item.remaining);

  function submit() {
    const lines = rx.items.flatMap((item) =>
      item.batches.map((b) => ({ itemId: item.id, batchId: b.id, quantity: qty(`${item.id}:${b.id}`) })).filter((l) => l.quantity > 0),
    );
    if (discountCentavos < 0) return setError("Enter the discount as an amount, like 25.00.");
    start(async () => {
      const result = await dispense({ prescriptionId: rx.id, lines, paymentMethod: payment, discountCentavos, notes: notes.trim() || null });
      if (result.ok) {
        toast.success("Dispensed, and the sale recorded", { description: `${result.data.number} · ${result.data.units} units` });
        router.push(`/pharmacy/dispensing/${result.data.id}`);
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
      {perItem.map(({ item, total }) => (
        <section key={item.id} className="rounded-[3px] border border-rule">
          <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule px-4 py-3">
            <div className="min-w-0">
              <h3 className="font-semibold text-ink">{item.medicine.label}</h3>
              <p className="text-meta text-ink-3">
                Written as “{item.writtenAs}”{item.directions ? ` · ${item.directions}` : ""}
              </p>
            </div>
            <p className="text-meta text-ink-2 tabular-nums">
              {item.remaining} of {item.quantity} owed · picking <span className="font-semibold text-ink">{total}</span>
              {total > item.remaining && (
                <span className="ml-2">
                  <Flag letter="!">more than owed</Flag>
                </span>
              )}
            </p>
          </header>
          {item.remaining === 0 ? (
            <p className="px-4 py-3 text-meta text-ink-3">Already dispensed in full.</p>
          ) : item.batches.length === 0 ? (
            <p className="px-4 py-3">
              <Flag letter="!">No eligible batch: none in stock that is available and unexpired.</Flag>
            </p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-caps text-ink-3 uppercase">
                  <th scope="col" className="py-2 pr-3 pl-4 font-semibold">Batch</th>
                  <th scope="col" className="px-3 py-2 font-semibold">Expires</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">On hand</th>
                  <th scope="col" className="py-2 pr-4 pl-3 text-right font-semibold">Give</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule border-t border-rule">
                {item.batches.map((b, n) => {
                  const key = `${item.id}:${b.id}`;
                  return (
                    <tr key={b.id}>
                      <td className="py-2 pr-3 pl-4">
                        Lot {b.lotNo}
                        {n === 0 && <span className="ml-2 text-meta text-ink-3">expires first</span>}
                      </td>
                      <td className="px-3 py-2 text-ink-2">{fmt.dateLabel(b.expiresOn)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{b.qtyOnHand}</td>
                      <td className="py-2 pr-4 pl-3 text-right">
                        <CellInput
                          className="w-20"
                          inputMode="numeric"
                          aria-label={`${item.medicine.label}, lot ${b.lotNo}: how many to give`}
                          aria-invalid={qty(key) > b.qtyOnHand || undefined}
                          value={picked[key] ?? ""}
                          onChange={(e) => setPicked({ ...picked, [key]: e.target.value.replace(/\D/g, "") })}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>
      ))}

      <FormGrid>
        <div className="sm:col-span-4">
          <Choice
            name="payment"
            legend="Paid by"
            value={payment}
            onChange={setPayment}
            options={(Object.keys(PAYMENT_METHODS) as PaymentMethod[]).map((m) => ({ value: m, label: PAYMENT_METHODS[m] }))}
          />
        </div>
        <Field label={`Discount (${fmt.symbol})`} size="sm" optional hint="Senior citizen, PWD or other discount, as an amount.">
          {(p) => <Input {...p} inputMode="decimal" value={discount} onChange={(e) => setDiscount(e.target.value)} placeholder="0.00" />}
        </Field>
        <Field label="Counselling or notes" size="full" optional>
          {(p) => <Textarea {...p} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} />}
        </Field>
      </FormGrid>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-4">
        <p className="text-sm text-ink-2">
          {units} unit{units === 1 ? "" : "s"} · <span className="font-semibold text-ink">{fmt.peso(Math.max(0, subtotal - Math.max(0, discountCentavos)))}</span>
          {discountCentavos > 0 && <span className="text-ink-3"> after {fmt.peso(discountCentavos)} off {fmt.peso(subtotal)}</span>}
        </p>
        <div className="flex flex-wrap gap-2">
          <LinkButton href="/pharmacy/dispensing" variant="quiet">
            Cancel
          </LinkButton>
          <Button type="submit" variant="primary" loading={pending} disabled={units === 0 || over.length > 0} icon={<Pill className="size-4" aria-hidden />}>
            Dispense {units > 0 ? `${units} unit${units === 1 ? "" : "s"}` : ""}
          </Button>
        </div>
      </div>
      <FormError message={error} />
    </form>
  );
}
