"use client";

import { Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { CellInput, Field, FormError, Select, Textarea } from "@/src/platform/ui/field";
import { QuantityInput } from "./quantity";
import { Sheet } from "@/src/platform/ui/sheet";
import { addCountLine, countStep, createAdjustment, recordCounts, startCount } from "../actions/inventory";
import type { AdjustmentReason, BatchRow, Count, ReasonOption, Reference } from "../lib/types";
import { useSave } from "./lines";
import { QuickAdd, WithAdd, type Added, type CanAdd } from "./quick-add";

type Row = { productId: string; locationId: string; batchId: string; batchNo: string; expiresOn: string; quantity: string; serials: string };
const blank = (): Row => ({ productId: "", locationId: "", batchId: "", batchNo: "", expiresOn: "", quantity: "", serials: "" });
const cell = "h-8 w-full rounded-lg border border-rule-strong bg-sheet px-2 text-sm hover:border-control focus:border-hema focus:outline-none";

/**
 * Writing up an adjustment: where, why, and what changes. Someone who may
 * approve adjustments posts it at once; anyone else's waits for them.
 */
export function AdjustmentForm({ reference, reasons, batches, approves, preset, canAdd = {} }: {
  canAdd?: CanAdd;
  reference: Pick<Reference, "products" | "units" | "warehouses">;
  reasons: ReasonOption[];
  /** Every batch with stock, for picking which one. */
  batches: BatchRow[];
  approves: boolean;
  preset?: { reason?: string; warehouseId?: string };
}) {
  const { pending, error, fields, save, shakeClass, anticipateClass } = useSave();
  const warehouses = reference.warehouses.filter((w) => w.isActive);
  const [warehouseId, setWarehouseId] = useState(preset?.warehouseId || warehouses[0]?.id || "");
  const [reason, setReason] = useState<AdjustmentReason>((reasons.find((r) => r.key === preset?.reason)?.key ?? "count") as AdjustmentReason);
  const [notes, setNotes] = useState("");
  const [rows, setRows] = useState<Row[]>([blank()]);
  // Products added from here, listed until the page's own list has them.
  const [fresh, setFresh] = useState<Added[]>([]);
  const products = [
    ...reference.products,
    ...fresh.filter((a) => !reference.products.some((p) => p.id === a.value)).map((a) => ({ id: a.value, sku: a.product!.sku, name: a.product!.name, unit: a.product!.unit, costPrice: a.product!.costPrice, sellingPrice: a.product!.sellingPrice, status: "active" as const, supplierId: null, trackBatches: a.product!.trackBatches, trackExpiry: a.product!.trackExpiry, trackSerials: a.product!.trackSerials })),
  ];
  const byId = new Map(products.map((p) => [p.id, p]));
  const warehouse = reference.warehouses.find((w) => w.id === warehouseId);
  const direction = reasons.find((r) => r.key === reason)?.direction ?? "either";
  const adds = direction === "adds";

  const set = (i: number, change: Partial<Row>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...change } : r)));

  function submit() {
    const lines = rows
      .filter((r) => r.productId)
      .map((r) => ({
        productId: r.productId,
        locationId: r.locationId || null,
        batchId: r.batchId || null,
        batchNo: r.batchId ? null : r.batchNo.trim() || null,
        expiresOn: r.batchId ? null : r.expiresOn || null,
        quantity: Number(r.quantity.replace(/[^\d-]/g, "")) || 0,
        serials: r.serials.split(/[\s,]+/).filter(Boolean),
      }));
    save(() => createAdjustment({ warehouseId, reason, notes: notes.trim() || null, lines }), (out) => ({
      message: out.status === "posted" ? `${out.number} posted` : `${out.number} submitted for approval`,
      go: `/adjustments/${out.id}`,
    }));
  }

  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); submit(); }} className={`space-y-5 rounded-xl transition-all duration-300 ${shakeClass} ${anticipateClass}`}>
      <Sheet className="px-5 pt-4 pb-5 sm:px-6">
        <div className="grid gap-5 sm:grid-cols-2">
          <WithAdd can={canAdd.warehouse} add={<QuickAdd kind="warehouse" label="New" onAdded={(a) => { setFresh((l) => [...l, a]); setWarehouseId(a.value); setRows([blank()]); }} />}>
            <Field label="Warehouse" error={fields.warehouseId}>
              {(p) => <Select {...p} value={warehouseId} onChange={(e) => { setWarehouseId(e.target.value); setRows([blank()]); }}>{warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}{fresh.filter((a) => a.kind === "warehouse").map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}</Select>}
            </Field>
          </WithAdd>
          <Field label="Reason" error={fields.reason} hint={direction === "adds" ? "Adds stock." : direction === "removes" ? (reason === "damaged" ? "Marks stock as damaged: still on hand, but no longer available." : "Removes stock.") : "A negative quantity removes stock; a positive one adds it."}>
            {(p) => <Select {...p} value={reason} onChange={(e) => setReason(e.target.value as AdjustmentReason)}>{reasons.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}</Select>}
          </Field>
        </div>
      </Sheet>
      <Sheet className="px-5 pt-4 pb-4 sm:px-6">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[48rem] text-left text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-meta text-ink-3">
                <th className="py-2 pr-2 font-semibold">Product</th>
                <th className="w-36 px-2 py-2 font-semibold">Location</th>
                <th className="w-56 px-2 py-2 font-semibold">Batch</th>
                <th className="w-28 px-2 py-2 text-right font-semibold">{direction === "either" ? "Change (±)" : "Quantity"}</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {rows.map((r, i) => {
                const p = byId.get(r.productId);
                const own = batches.filter((b) => b.product.id === r.productId && (!warehouse || b.warehouses.some((w) => w.code === warehouse.code)));
                const err = fields[`lines.${i}.productId`] || fields[`lines.${i}.quantity`] || fields[`lines.${i}.batchId`] || fields[`lines.${i}.locationId`];
                // How much of the picked batch is here: the most a removal can take.
                const picked = own.find((b) => b.id === r.batchId);
                const hereOnHand = picked && warehouse ? picked.warehouses.find((w) => w.code === warehouse.code)?.onHand : undefined;
                return (
                  <tr key={i}>
                    <td className="py-2 pr-2 align-top">
                      <Select aria-label={`Line ${i + 1} product`} value={r.productId} onChange={(e) => set(i, { productId: e.target.value, batchId: "", batchNo: "" })}>
                        <option value="">Select a product…</option>
                        {products.map((x) => <option key={x.id} value={x.id}>{x.name} · {x.sku}</option>)}
                      </Select>
                      {p?.trackSerials && (
                        <Textarea aria-label={`Line ${i + 1} serial numbers`} rows={2} placeholder="Serial numbers, one per unit" value={r.serials} onChange={(e) => set(i, { serials: e.target.value })} className="mt-2 !min-h-14 font-mono text-meta" />
                      )}
                      {err && <p className="mt-1 text-meta text-danger">{err}</p>}
                    </td>
                    <td className="px-2 py-2 align-top">
                      <Select aria-label={`Line ${i + 1} location`} value={r.locationId} onChange={(e) => set(i, { locationId: e.target.value })}>
                        {warehouse?.locations.filter((l) => l.isActive).map((l) => <option key={l.id} value={l.isDefault ? "" : l.id}>{l.code}</option>)}
                      </Select>
                    </td>
                    <td className="px-2 py-2 align-top">
                      {p?.trackBatches ? (
                        <>
                          <Select aria-label={`Line ${i + 1} batch`} value={r.batchId} onChange={(e) => set(i, { batchId: e.target.value })}>
                            <option value="">{adds || direction === "either" ? "New batch…" : "Select a batch…"}</option>
                            {own.map((b) => <option key={b.id} value={b.id}>{b.batchNo} ({b.onHand}){b.expiresOn ? ` · ${b.expiresOn}` : ""}</option>)}
                          </Select>
                          {!r.batchId && (adds || direction === "either") && (
                            <div className="mt-1.5 flex gap-1.5">
                              <input aria-label="New batch number" placeholder="Batch number" value={r.batchNo} onChange={(e) => set(i, { batchNo: e.target.value })} className={`${cell} font-mono`} />
                              {p.trackExpiry && <input aria-label="Expiry date" type="date" value={r.expiresOn} onChange={(e) => set(i, { expiresOn: e.target.value })} className={cell} />}
                            </div>
                          )}
                        </>
                      ) : <span className="text-meta text-ink-3">—</span>}
                    </td>
                    <td className="px-2 py-2 align-top">
                      <QuantityInput
                        label={`Line ${i + 1} quantity`}
                        signed={direction === "either"}
                        placeholder={direction === "either" ? "-3" : ""}
                        value={r.quantity}
                        onChange={(quantity) => set(i, { quantity })}
                        className="w-24"
                        unit={p?.unit}
                        max={direction === "removes" && hereOnHand !== undefined ? hereOnHand : undefined}
                        min={direction === "either" && hereOnHand !== undefined ? -hereOnHand : undefined}
                      />
                    </td>
                    <td className="py-2 text-right align-top">
                      {rows.length > 1 && (
                        <button type="button" title="Remove this line" onClick={() => setRows(rows.filter((_, j) => j !== i))} className="rounded-md p-1.5 text-ink-3 hover:bg-bench hover:text-danger"><X className="size-4" aria-hidden /></button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1">
          <Button size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => setRows([...rows, blank()])}>Add line</Button>
          {canAdd.product && adds && (
            <QuickAdd
              kind="product"
              label="New product"
              context={{ units: reference.units.filter((u) => u.isActive) }}
              onAdded={(a) => {
                setFresh((list) => [...list, a]);
                const empty = rows.findIndex((r) => !r.productId);
                setRows(empty >= 0 ? rows.map((r, j) => (j === empty ? { ...r, productId: a.value } : r)) : [...rows, { ...blank(), productId: a.value }]);
              }}
            />
          )}
        </div>
      </Sheet>
      <Field label="Notes" optional error={fields.notes} hint="Recorded in the stock movement history.">
        {(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />}
      </Field>
      <FormError message={error ?? fields.lines} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>{approves ? "Post adjustment" : "Submit for approval"}</Button>
        <LinkButton href="/adjustments" variant="quiet">Cancel</LinkButton>
      </div>
    </form>
  );
}

/** Starting a count of one warehouse, or of one category in it. */
export function StartCount({ reference, warehouseId, canAdd = {} }: { reference: Pick<Reference, "categories" | "warehouses">; warehouseId?: string; canAdd?: CanAdd }) {
  const { pending, error, fields, save } = useSave();
  const [w, setW] = useState(warehouseId || reference.warehouses.find((x) => x.isActive)?.id || "");
  const [category, setCategory] = useState("");
  const [added, setAdded] = useState<Added[]>([]);
  const newOnes = (kind: Added["kind"]) => added.filter((a) => a.kind === kind).map((a) => <option key={a.value} value={a.value}>{a.label}</option>);
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="min-w-48">
        <WithAdd can={canAdd.warehouse} add={<QuickAdd kind="warehouse" label="New" onAdded={(a) => { setAdded((l) => [...l, a]); setW(a.value); }} />}>
          <Field label="Warehouse" error={fields.warehouseId}>
            {(p) => <Select {...p} value={w} onChange={(e) => setW(e.target.value)}>{reference.warehouses.filter((x) => x.isActive).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}{newOnes("warehouse")}</Select>}
          </Field>
        </WithAdd>
      </div>
      <Field label="Category" optional className="min-w-56">
        {(p) => <Select {...p} value={category} onChange={(e) => setCategory(e.target.value)}><option value="">All categories</option>{reference.categories.map((c) => <option key={c.id} value={c.id}>{c.path}</option>)}</Select>}
      </Field>
      <Button variant="primary" loading={pending} onClick={() => save(() => startCount({ warehouseId: w, categoryId: category || null }), (out) => ({ message: `${out.number} started`, go: `/counts/${out.id}` }))}>
        Start count
      </Button>
      {error && <div className="w-full"><FormError message={error} /></div>}
    </div>
  );
}

/**
 * The count sheet: what the system expected on each line, and what was
 * found. Blank means not counted yet. Differences show as they're typed.
 */
export function CountSheet({ count, reference, canCount, day }: { count: Count; reference: Pick<Reference, "products">; canCount: boolean; day: Record<string, string> }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [shaking, setShaking] = useState(false);
  const open = count.status === "open" && canCount;
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(count.lines.map((l) => [l.id, l.counted == null ? "" : String(l.counted)])));
  const [error, setError] = useState<string | null>(null);
  const [extra, setExtra] = useState({ productId: "", counted: "" });
  const dirty = count.lines.some((l) => (values[l.id] ?? "") !== (l.counted == null ? "" : String(l.counted)));

  function triggerShake() {
    setShaking(true);
    setTimeout(() => setShaking(false), 480);
  }

  function persist(then?: () => Promise<{ ok: boolean; error?: string }>, message = "Counts saved") {
    start(async () => {
      try {
        if (dirty) {
          const r = await recordCounts(count.id, count.lines.map((l) => ({ lineId: l.id, counted: values[l.id] === "" ? null : Number(values[l.id]) })));
          if (!r.ok) {
            triggerShake();
            toast.error(r.error || "Could not save counts.");
            return setError(r.error);
          }
        }
        if (then) {
          const r = await then();
          if (!r.ok) {
            triggerShake();
            const err = r.error ?? "Something went wrong.";
            toast.error(err);
            return setError(err);
          }
        }
        setError(null);
        toast.success(message);
        router.refresh();
      } catch (err) {
        triggerShake();
        const errText = err instanceof Error ? err.message : "Network error. Please try again.";
        setError(errText);
        toast.error(errText);
      }
    });
  }

  return (
    <div className={`rounded-xl transition-all duration-300 ${shaking ? "animate-shake ring-2 ring-danger/40 ring-offset-2" : ""} ${pending ? "animate-anticipate pointer-events-none opacity-90" : ""}`}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[44rem] text-left text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-meta text-ink-3">
              <th className="py-3 pr-3 pl-5 font-semibold">Product</th>
              <th className="px-3 py-3 font-semibold">Location · batch</th>
              <th className="px-3 py-3 text-right font-semibold">Expected</th>
              <th className="px-3 py-3 text-right font-semibold">Counted</th>
              <th className="py-3 pr-5 pl-3 text-right font-semibold">Variance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {count.lines.map((l) => {
              const v = values[l.id];
              const diff = v === "" || v === undefined ? null : Number(v) - l.expected;
              return (
                <tr key={l.id}>
                  <td className="py-2 pr-3 pl-5">{l.product.name}<span className="block text-meta text-ink-3">{l.product.sku}</span></td>
                  <td className="px-3 py-2 text-ink-2">{l.location.code}{l.batch && <span className="font-mono"> · {l.batch.batchNo}</span>}{l.batch?.expiresOn && <span className="block text-meta text-ink-3">exp. {day[l.batch.expiresOn] ?? l.batch.expiresOn}</span>}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{l.expected}</td>
                  <td className="px-3 py-2 text-right">
                    {open ? (
                      <CellInput aria-label={`${l.product.name} counted`} inputMode="numeric" value={v} onChange={(e) => setValues({ ...values, [l.id]: e.target.value.replace(/\D/g, "") })} className="w-20" />
                    ) : (
                      <span className="tabular-nums">{l.counted ?? "—"}</span>
                    )}
                  </td>
                  <td className={`py-2 pr-5 pl-3 text-right font-semibold tabular-nums ${diff ? "text-eosin" : "text-ink-3"}`}>{diff === null ? "" : diff > 0 ? `+${diff}` : diff}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {open && (
        <div className="space-y-3 border-t border-rule px-5 py-4">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-meta text-ink-2">Add an item not on the count sheet</span>
            <Select aria-label="Product" value={extra.productId} onChange={(e) => setExtra({ ...extra, productId: e.target.value })} className="min-w-56">
              <option value="">Product…</option>
              {reference.products.filter((p) => !p.trackBatches).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </Select>
            <CellInput aria-label="Counted quantity" placeholder="0" value={extra.counted} onChange={(e) => setExtra({ ...extra, counted: e.target.value.replace(/\D/g, "") })} className="w-20" />
            <Button size="sm" disabled={!extra.productId} loading={pending} onClick={() => persist(async () => { const r = await addCountLine(count.id, { productId: extra.productId, counted: Number(extra.counted) || 0 }); if (r.ok) setExtra({ productId: "", counted: "" }); return r; }, "Line added")}>
              Add line
            </Button>
          </div>
          <FormError message={error} />
          <div className="flex flex-wrap gap-2">
            <Button loading={pending} disabled={!dirty} onClick={() => persist()}>Save counts</Button>
            <Button variant="primary" loading={pending} onClick={() => persist(() => countStep(count.id, "submit"), "Count submitted for approval")}>Submit count</Button>
          </div>
        </div>
      )}
    </div>
  );
}
