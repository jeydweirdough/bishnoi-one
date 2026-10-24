"use client";

import { Undo2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/pharmacy/platform/ui/button";
import { CellInput, Choice, Field, FormError, Input } from "@/src/modules/pharmacy/platform/ui/field";
import { makeFormat } from "@/src/modules/pharmacy/platform/lib/format";
import type { Org } from "@/src/modules/pharmacy/platform/lib/types";
import { makeReturn } from "@/src/modules/pharmacy/actions/pharmacy";
import { PAYMENT_METHODS } from "@/src/modules/pharmacy/lib/words";
import type { PaymentMethod, Sale } from "@/src/modules/pharmacy/lib/types";

/**
 * Medicines brought back on this sale. They go back on the shelf only when
 * sealed and undamaged; the refund is whatever is paid back, which may be
 * nothing (an exchange).
 */
export function ReturnForm({ sale, org }: { sale: Sale; org: Org }) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const [pending, start] = useTransition();
  const [open, setOpen] = useState(false);
  const [qty, setQty] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [restock, setRestock] = useState<"yes" | "no">("no");
  const [refund, setRefund] = useState("");
  const [method, setMethod] = useState<PaymentMethod>(sale.paymentMethod);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  const returnable = sale.lines.filter((l) => l.quantity > l.qtyReturned);
  const value = returnable.reduce((s, l) => s + (Number.parseInt(qty[l.id] || "0", 10) || 0) * l.unitPriceCentavos, 0);
  const maxRefund = Math.min(value, sale.totalCentavos - sale.refundedCentavos);

  if (returnable.length === 0) return <p className="text-meta text-ink-3">Everything on this sale has been returned.</p>;
  if (!open) {
    return (
      <Button onClick={() => setOpen(true)} icon={<Undo2 className="size-4" aria-hidden />}>
        Return items on {sale.number}
      </Button>
    );
  }

  function submit() {
    const refundCentavos = refund ? fmt.toCentavos(refund) : 0;
    if (refundCentavos === null) return setFields({ refundCentavos: "Enter an amount like 45.00." });
    start(async () => {
      const result = await makeReturn(sale.id, {
        lines: returnable.map((l) => ({ saleLineId: l.id, quantity: Number.parseInt(qty[l.id] || "0", 10) || 0 })).filter((l) => l.quantity > 0),
        reason: reason.trim(),
        restock: restock === "yes",
        refundCentavos,
        refundMethod: refundCentavos ? method : null,
      });
      if (result.ok) {
        toast.success(refundCentavos ? "Returned and refunded" : "Return recorded");
        setOpen(false);
        setQty({});
        setReason("");
        setRefund("");
        router.refresh();
        return;
      }
      setError(result.error);
      setFields(result.fields ?? {});
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-5"
    >
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="text-caps text-ink-3 uppercase">
            <th scope="col" className="py-2 pr-3 font-semibold">Medicine</th>
            <th scope="col" className="px-3 py-2 text-right font-semibold">Can return</th>
            <th scope="col" className="py-2 pl-3 text-right font-semibold">Returning</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule border-t border-rule">
          {returnable.map((l) => (
            <tr key={l.id}>
              <td className="py-2 pr-3">
                {l.medicine} <span className="text-meta text-ink-3">· lot {l.lotNo}</span>
              </td>
              <td className="px-3 py-2 text-right tabular-nums">{l.quantity - l.qtyReturned}</td>
              <td className="py-2 pl-3 text-right">
                <CellInput
                  className="w-20"
                  inputMode="numeric"
                  aria-label={`${l.medicine}: how many are coming back`}
                  value={qty[l.id] ?? ""}
                  onChange={(e) => setQty({ ...qty, [l.id]: e.target.value.replace(/\D/g, "") })}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Field label="Reason" error={fields.reason}>
        {(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="Wrong item, adverse reaction, damaged…" />}
      </Field>
      <Choice
        name="restock"
        legend="Back on the shelf?"
        value={restock}
        onChange={setRestock}
        options={[
          { value: "no", label: "No: opened, damaged or unsure" },
          { value: "yes", label: "Yes: sealed and undamaged" },
        ]}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={`Refund (${fmt.symbol})`} optional error={fields.refundCentavos} hint={`Up to ${fmt.peso(Math.max(0, maxRefund))}.`}>
          {(p) => <Input {...p} inputMode="decimal" value={refund} onChange={(e) => setRefund(e.target.value)} placeholder="0.00" />}
        </Field>
        {refund && (
          <Choice
            name="method"
            legend="Paid back by"
            value={method}
            onChange={setMethod}
            options={(Object.keys(PAYMENT_METHODS) as PaymentMethod[]).map((m) => ({ value: m, label: PAYMENT_METHODS[m] }))}
          />
        )}
      </div>
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending} disabled={value === 0}>
          Record return
        </Button>
        <Button variant="quiet" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
