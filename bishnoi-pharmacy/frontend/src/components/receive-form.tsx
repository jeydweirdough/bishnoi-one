"use client";

import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { receiveStock } from "../actions/pharmacy";

type Line = { medicineId: string; lotNo: string; expiresOn: string; manufacturedOn: string; quantity: string; cost: string };
const blank = (): Line => ({ medicineId: "", lotNo: "", expiresOn: "", manufacturedOn: "", quantity: "", cost: "" });

/** Taking a delivery in: one line per lot, each with its own expiry. */
export function ReceiveForm({ medicines, suppliers, org }: { medicines: { id: string; label: string; unit: string }[]; suppliers: { id: string; name: string }[]; org: Org }) {
  const fmt = makeFormat(org);
  const today = fmt.todayKey();
  const router = useRouter();
  const [pending, start] = useTransition();
  const [head, setHead] = useState({ supplierId: "", reference: "", receivedOn: today, notes: "" });
  const [lines, setLines] = useState<Line[]>([blank()]);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const setLine = (n: number, change: Partial<Line>) => setLines(lines.map((l, i) => (i === n ? { ...l, ...change } : l)));

  function submit() {
    const bad = lines.findIndex((l) => l.cost && fmt.toCentavos(l.cost) === null);
    if (bad >= 0) return setFields({ [`lines.${bad}.costCentavos`]: "Enter a cost like 7.10." });
    start(async () => {
      const result = await receiveStock({
        supplierId: head.supplierId || null,
        reference: head.reference.trim() || null,
        receivedOn: head.receivedOn,
        notes: head.notes.trim() || null,
        lines: lines.map((l) => ({
          medicineId: l.medicineId,
          lotNo: l.lotNo.trim(),
          expiresOn: l.expiresOn,
          manufacturedOn: l.manufacturedOn || null,
          quantity: Number.parseInt(l.quantity, 10) || 0,
          costCentavos: fmt.toCentavos(l.cost || "0") ?? 0,
        })),
      });
      if (result.ok) {
        toast.success("Stock received", { description: `${result.data.number} · ${result.data.units} units` });
        router.push(`/stock/receivings/${result.data.id}`);
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
      className="space-y-6"
    >
      <div className="grid gap-5 sm:grid-cols-3">
        <Field label="Supplier" optional error={fields.supplierId}>
          {(p) => (
            <Select {...p} value={head.supplierId} onChange={(e) => setHead({ ...head, supplierId: e.target.value })}>
              <option value="">Not on record</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Their invoice or DR no." optional>
          {(p) => <Input {...p} value={head.reference} onChange={(e) => setHead({ ...head, reference: e.target.value })} />}
        </Field>
        <Field label="Received on" error={fields.receivedOn}>
          {(p) => <Input {...p} type="date" max={today} value={head.receivedOn} onChange={(e) => setHead({ ...head, receivedOn: e.target.value })} />}
        </Field>
      </div>

      <fieldset className="space-y-3">
        <legend className="mb-2 text-heading text-ink">Lots</legend>
        {lines.map((l, n) => (
          <div key={n} className="grid gap-3 rounded-[3px] border border-rule p-3 sm:grid-cols-6">
            <Field label="Medicine" className="sm:col-span-3" error={fields[`lines.${n}.medicineId`]}>
              {(p) => (
                <Select {...p} value={l.medicineId} onChange={(e) => setLine(n, { medicineId: e.target.value })}>
                  <option value="">Pick a medicine</option>
                  {medicines.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Lot no." className="sm:col-span-2" error={fields[`lines.${n}.lotNo`]}>
              {(p) => <Input {...p} value={l.lotNo} onChange={(e) => setLine(n, { lotNo: e.target.value.toUpperCase() })} />}
            </Field>
            <div className="flex items-end justify-end">
              <Button
                size="sm"
                variant="quiet"
                disabled={lines.length === 1}
                onClick={() => setLines(lines.filter((_, i) => i !== n))}
                title="Remove this lot"
                aria-label={`Remove lot ${n + 1}`}
                icon={<Trash2 className="size-4" aria-hidden />}
              />
            </div>
            <Field label="Expires" className="sm:col-span-2" error={fields[`lines.${n}.expiresOn`]}>
              {(p) => <Input {...p} type="date" min={today} value={l.expiresOn} onChange={(e) => setLine(n, { expiresOn: e.target.value })} />}
            </Field>
            <Field label="Made" optional className="sm:col-span-2" error={fields[`lines.${n}.manufacturedOn`]}>
              {(p) => <Input {...p} type="date" max={today} value={l.manufacturedOn} onChange={(e) => setLine(n, { manufacturedOn: e.target.value })} />}
            </Field>
            <Field label={`Quantity${l.medicineId ? ` (${medicines.find((m) => m.id === l.medicineId)?.unit ?? "units"})` : ""}`} error={fields[`lines.${n}.quantity`]}>
              {(p) => <Input {...p} inputMode="numeric" value={l.quantity} onChange={(e) => setLine(n, { quantity: e.target.value.replace(/\D/g, "") })} />}
            </Field>
            <Field label={`Unit cost (${fmt.symbol})`} optional error={fields[`lines.${n}.costCentavos`]}>
              {(p) => <Input {...p} inputMode="decimal" value={l.cost} onChange={(e) => setLine(n, { cost: e.target.value })} placeholder="0.00" />}
            </Field>
          </div>
        ))}
        <Button size="sm" onClick={() => setLines([...lines, blank()])} icon={<Plus className="size-4" aria-hidden />} disabled={lines.length >= 200}>
          Add a lot
        </Button>
      </fieldset>

      <Field label="Notes" optional>
        {(p) => <Textarea {...p} value={head.notes} onChange={(e) => setHead({ ...head, notes: e.target.value })} maxLength={2000} />}
      </Field>
      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          Receive {lines.reduce((s, l) => s + (Number.parseInt(l.quantity, 10) || 0), 0) || ""} units
        </Button>
        <LinkButton href="/stock?view=receiving" variant="quiet">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}
