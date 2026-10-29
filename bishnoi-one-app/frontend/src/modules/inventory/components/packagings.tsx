"use client";

import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { deletePackaging, savePackaging } from "@/src/modules/inventory/actions/inventory";
import type { PackagingRow } from "@/src/modules/inventory/lib/types";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input } from "@/src/platform/ui/field";

// Units with conversions (feature plan step 14e): an item's packs. Stock stays in its base unit; forms let people
// type in packs, a pack's barcode scans as the whole pack, and quantities can be shown in packs.

/** A quantity in the base unit, written in packs too: 1,050 → "10 Box + 5 Strip" (biggest first). */
export function inPacks(quantity: number, packs: PackagingRow[], unit: string): string | null {
  if (!packs.length || quantity <= 0) return null;
  let left = quantity;
  const parts: string[] = [];
  for (const p of [...packs].sort((a, b) => b.quantity - a.quantity)) {
    const n = Math.floor(left / p.quantity);
    if (n > 0) {
      parts.push(`${n.toLocaleString()} ${p.name}`);
      left -= n * p.quantity;
    }
  }
  if (!parts.length) return null;
  if (left > 0) parts.push(`${left.toLocaleString()} ${unit}`);
  return parts.join(" + ");
}

export function PackagingsEditor({ productId, unit, packs, canEdit }: { productId: string; unit: string; packs: PackagingRow[]; canEdit: boolean }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [form, setForm] = useState({ name: "", quantity: "", barcode: "" });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  function add() {
    start(async () => {
      const r = await savePackaging(productId, null, { name: form.name.trim(), quantity: Number(form.quantity) || 0, barcode: form.barcode.trim() || null });
      if (!r.ok) {
        setFields(r.fields ?? {});
        return setError(r.fields ? null : r.error);
      }
      toast.success(`${form.name.trim()} added`);
      setForm({ name: "", quantity: "", barcode: "" });
      setFields({});
      setError(null);
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
        <form noValidate onSubmit={(e) => (e.preventDefault(), add())} className="mt-3 grid items-end gap-3 sm:grid-cols-[1fr_8rem_1fr_auto]">
          <Field label="Pack" error={fields.name}>{(p) => <Input {...p} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={40} placeholder="Box" />}</Field>
          <Field label={`How many ${unit}`} error={fields.quantity}>{(p) => <Input {...p} inputMode="numeric" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} placeholder="100" />}</Field>
          <Field label="Barcode" optional error={fields.barcode}>{(p) => <Input {...p} value={form.barcode} onChange={(e) => setForm({ ...form, barcode: e.target.value })} maxLength={64} />}</Field>
          <Button type="submit" size="sm" icon={<Plus className="size-4" aria-hidden />} loading={busy}>Add pack</Button>
          <div className="sm:col-span-4"><FormError message={error} /></div>
        </form>
      )}
    </div>
  );
}
