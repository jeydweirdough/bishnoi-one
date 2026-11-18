"use client";

import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { deletePackaging, savePackaging, saveProduct } from "@/src/modules/inventory/actions/inventory";
import type { PackagingRow } from "@/src/modules/inventory/lib/types";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input } from "@/src/platform/ui/field";

export { inPacks } from "@/src/modules/inventory/lib/packs";

// Units with conversions (feature plan step 14e): an item's packs. Stock stays in its base unit; forms let people
// type in packs, a pack's barcode scans as the whole pack, and quantities can be shown in packs.
// Packs that can be broken (step 4A): each level says whether it may be sold and may have its own price.

const peso = (c: number) => `₱${(c / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const centavos = (text: string): number | null => {
  const n = Number(text.replace(/[₱,\s]/g, ""));
  return text.trim() === "" || !Number.isFinite(n) ? null : Math.round(n * 100);
};

export function PackagingsEditor({ productId, unit, packs, canEdit, baseSellable = true, sellingPrice = 0 }: {
  productId: string; unit: string; packs: PackagingRow[]; canEdit: boolean; baseSellable?: boolean; sellingPrice?: number;
}) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [form, setForm] = useState({ name: "", quantity: "", barcode: "", price: "", sellable: true });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  function add() {
    start(async () => {
      const r = await savePackaging(productId, null, { name: form.name.trim(), quantity: Number(form.quantity) || 0, barcode: form.barcode.trim() || null,
        sellable: form.sellable, price: centavos(form.price) });
      if (!r.ok) {
        setFields(r.fields ?? {});
        return setError(r.fields ? null : r.error);
      }
      toast.success(`${form.name.trim()} added`);
      setForm({ name: "", quantity: "", barcode: "", price: "", sellable: true });
      setFields({});
      setError(null);
      router.refresh();
    });
  }

  function change(run: () => Promise<{ ok: boolean; error?: string }>, done: string) {
    start(async () => {
      const r = await run();
      if (!r.ok) return void toast.error(r.error ?? "Couldn't save.");
      toast.success(done);
      router.refresh();
    });
  }

  function remove(p: PackagingRow) {
    start(async () => {
      const r = await deletePackaging(productId, p.id);
      if (!r.ok) return void toast.error(r.error);
      toast.success(`${p.name} removed`);
      router.refresh();
    });
  }

  return (
    <div>
      {packs.length > 0 && (
        <label className="mb-2 flex items-center gap-2 text-sm text-ink-2">
          <input suppressHydrationWarning type="checkbox" checked={baseSellable} disabled={!canEdit || busy}
            onChange={(e) => change(() => saveProduct(productId, { baseSellable: e.target.checked }), e.target.checked ? `Sold by the ${unit}` : `Not sold by the ${unit}`)} />
          Sold by the {unit} ({peso(sellingPrice)})
        </label>
      )}
      {packs.length === 0 ? (
        <p className="text-meta text-ink-3">Counted in {unit} only. Add its packs (Strip, Box, Case) to enter and see quantities in them.</p>
      ) : (
        <ul className="divide-y divide-rule text-sm">
          {packs.map((p) => (
            <li key={p.id} className="flex items-center gap-3 py-1.5">
              <span className="font-medium text-ink">1 {p.name}</span>
              <span className="text-ink-2">= {p.quantity.toLocaleString()} {unit}</span>
              {p.barcode && <span className="font-mono text-meta text-ink-3">{p.barcode}</span>}
              <span className="flex-1" />
              <span className="text-meta text-ink-2 tabular-nums" title={p.price == null ? `${unit} price × ${p.quantity}` : "Its own price"}>
                {peso(p.price ?? sellingPrice * p.quantity)}
              </span>
              <label className="flex items-center gap-1.5 text-meta text-ink-2">
                <input suppressHydrationWarning type="checkbox" checked={p.sellable !== false} disabled={!canEdit || busy}
                  onChange={(e) => change(() => savePackaging(productId, p.id, { sellable: e.target.checked }), e.target.checked ? `${p.name} can be sold` : `${p.name} not sold`)} />
                Sold
              </label>
              {canEdit && (
                <button suppressHydrationWarning type="button" title={`Remove ${p.name}`} disabled={busy} onClick={() => remove(p)} className="rounded-md p-1 text-ink-3 hover:text-danger">
                  <Trash2 className="size-4" aria-hidden />
                  <span className="sr-only">Remove {p.name}</span>
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        <form noValidate onSubmit={(e) => (e.preventDefault(), add())} className="mt-3 grid items-end gap-3 sm:grid-cols-[1fr_7rem_1fr_8rem_auto_auto]">
          <Field label="Pack" error={fields.name}>{(p) => <Input {...p} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={40} placeholder="Box" />}</Field>
          <Field label={`How many ${unit}`} error={fields.quantity}>{(p) => <Input {...p} inputMode="numeric" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} placeholder="100" />}</Field>
          <Field label="Barcode" optional error={fields.barcode}>{(p) => <Input {...p} value={form.barcode} onChange={(e) => setForm({ ...form, barcode: e.target.value })} maxLength={64} />}</Field>
          <Field label="Price" optional hint={`Empty: ${unit} price × quantity`} error={fields.price}>{(p) => <Input {...p} inputMode="decimal" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} placeholder="0.00" />}</Field>
          <label className="flex h-10 items-center gap-1.5 text-sm text-ink-2">
            <input suppressHydrationWarning type="checkbox" checked={form.sellable} onChange={(e) => setForm({ ...form, sellable: e.target.checked })} />
            Sold
          </label>
          <Button type="submit" size="sm" icon={<Plus className="size-4" aria-hidden />} loading={busy}>Add pack</Button>
          <div className="sm:col-span-6"><FormError message={error} /></div>
        </form>
      )}
    </div>
  );
}
