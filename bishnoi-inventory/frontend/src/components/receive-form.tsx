"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { CellInput, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { receiveDelivery } from "../actions/inventory";
import type { PO, Reference } from "../lib/types";
import { useSave } from "./lines";
import { QuickAdd, WithAdd, type Added, type CanAdd } from "./quick-add";

type Row = { productId: string; orderLineId: string | null; quantity: string; cost: string; batchNo: string; manufacturedOn: string; expiresOn: string; serials: string; outstanding: number | null };

const cell = "h-8 rounded-lg border border-rule-strong bg-sheet px-2 text-sm hover:border-control focus:border-hema focus:outline-none";

/**
 * Taking a delivery in. Against a purchase order, its outstanding lines are
 * filled in; each line takes its batch, expiry and serial numbers as the
 * product needs them.
 */
export function ReceiveForm({ org, reference, order, canAdd = {} }: { org: Org; reference: Pick<Reference, "products" | "suppliers" | "units" | "warehouses">; order?: PO; canAdd?: CanAdd }) {
  const fmt = makeFormat(org);
  const { pending, error, fields, save, shakeClass, anticipateClass } = useSave();
  // Added from here ("+ New …"), listed until the page's own lists have them.
  const [added, setAdded] = useState<Added[]>([]);
  const remember = (a: Added) => setAdded((list) => [...list, a]);
  const addedOf = (kind: Added["kind"], have: Set<string>) => added.filter((a) => a.kind === kind && !have.has(a.value));
  const products = [
    ...reference.products,
    ...addedOf("product", new Set(reference.products.map((p) => p.id))).map((a) => ({ id: a.value, sku: a.product!.sku, name: a.product!.name, unit: a.product!.unit, costPrice: a.product!.costPrice, sellingPrice: a.product!.sellingPrice, status: "active" as const, supplierId: null, trackBatches: a.product!.trackBatches, trackExpiry: a.product!.trackExpiry, trackSerials: a.product!.trackSerials })),
  ];
  const byId = new Map(products.map((p) => [p.id, p]));
  const [supplierId, setSupplierId] = useState(order?.supplier.id ?? "");
  const [warehouseId, setWarehouseId] = useState(order?.warehouse.id ?? reference.warehouses.find((w) => w.isActive)?.id ?? "");
  const [locationId, setLocationId] = useState("");
  const [deliveryRef, setDeliveryRef] = useState("");
  const [notes, setNotes] = useState("");
  const blank = (): Row => ({ productId: "", orderLineId: null, quantity: "", cost: "", batchNo: "", manufacturedOn: "", expiresOn: "", serials: "", outstanding: null });
  const [rows, setRows] = useState<Row[]>(() =>
    order
      ? order.lines.filter((l) => l.outstanding > 0).map((l) => ({ ...blank(), productId: l.product.id, orderLineId: l.id, quantity: String(l.outstanding), cost: fmt.pesosText(l.unitCost), outstanding: l.outstanding }))
      : [blank()],
  );
  const locations = [
    ...(reference.warehouses.find((w) => w.id === warehouseId)?.locations.filter((l) => l.isActive) ?? []),
    ...added.filter((a) => a.kind === "location").map((a) => ({ id: a.value, code: a.label.split(" · ")[0], name: a.label.split(" · ").slice(1).join(" · "), isDefault: false, isActive: true })),
  ];
  const suppliers = [...reference.suppliers.filter((s) => s.isActive).map((s) => ({ value: s.id, label: s.name })), ...addedOf("supplier", new Set(reference.suppliers.map((s) => s.id))).map((a) => ({ value: a.value, label: a.label }))];
  const warehouses = [...reference.warehouses.filter((w) => w.isActive).map((w) => ({ value: w.id, label: w.name })), ...addedOf("warehouse", new Set(reference.warehouses.map((w) => w.id))).map((a) => ({ value: a.value, label: a.label }))];

  /** A product made from here goes on the first empty line. */
  function productAdded(a: Added) {
    remember(a);
    const empty = rows.findIndex((r) => !r.productId);
    const row = { ...blank(), productId: a.value, cost: fmt.pesosText(a.product?.costPrice ?? 0) };
    setRows(empty >= 0 ? rows.map((r, j) => (j === empty ? { ...row, quantity: r.quantity } : r)) : [...rows, row]);
  }

  const set = (i: number, change: Partial<Row>) =>
    setRows(rows.map((r, j) => {
      if (j !== i) return r;
      const next = { ...r, ...change };
      if (change.productId && !r.cost) next.cost = fmt.pesosText(byId.get(change.productId)?.costPrice ?? 0);
      return next;
    }));

  function submit() {
    const lines = rows
      .filter((r) => r.productId && Number(r.quantity) > 0)
      .map((r) => ({
        productId: r.productId,
        orderLineId: r.orderLineId,
        quantity: Number(r.quantity),
        unitCost: r.cost ? fmt.toCentavos(r.cost) : null,
        batchNo: r.batchNo.trim() || null,
        manufacturedOn: r.manufacturedOn || null,
        expiresOn: r.expiresOn || null,
        serials: r.serials.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean),
      }));
    const input = { orderId: order?.id ?? null, supplierId: order ? null : supplierId || null, warehouseId, locationId: locationId || null, deliveryRef: deliveryRef.trim() || null, notes: notes.trim() || null, lines };
    save(() => receiveDelivery(input), (out) => ({ message: `${out.number} received${out.orderStatus === "partial" ? ": part of the order is still to come" : ""}`, go: `/receipts/${out.id}` }));
  }

  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); submit(); }} className={`space-y-5 rounded-xl transition-all duration-300 ${shakeClass} ${anticipateClass}`}>
      <Sheet className="px-5 pt-4 pb-5 sm:px-6">
        <div className="grid gap-5 sm:grid-cols-4">
          {!order && (
            <WithAdd can={canAdd.supplier} add={<QuickAdd kind="supplier" label="New" onAdded={(a) => { remember(a); setSupplierId(a.value); }} />}>
              <Field label="Supplier" optional error={fields.supplierId}>
                {(p) => (
                  <Select {...p} value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
                    <option value="">None</option>
                    {suppliers.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                  </Select>
                )}
              </Field>
            </WithAdd>
          )}
          <WithAdd can={canAdd.warehouse && !order} add={<QuickAdd kind="warehouse" label="New" onAdded={(a) => { remember(a); setWarehouseId(a.value); setLocationId(""); }} />}>
            <Field label="Into warehouse" error={fields.warehouseId}>
              {(p) => (
                <Select {...p} value={warehouseId} onChange={(e) => { setWarehouseId(e.target.value); setLocationId(""); }}>
                  {warehouses.map((w) => <option key={w.value} value={w.value}>{w.label}</option>)}
                </Select>
              )}
            </Field>
          </WithAdd>
          <WithAdd can={canAdd.location} add={<QuickAdd kind="location" label="New" context={{ warehouseId }} onAdded={(a) => { remember(a); setLocationId(a.value); }} />}>
          <Field label="Location" error={fields.locationId}>
            {(p) => (
              <Select {...p} value={locationId} onChange={(e) => setLocationId(e.target.value)}>
                {locations.map((l) => <option key={l.id} value={l.isDefault ? "" : l.id}>{l.code} · {l.name}{l.isDefault ? " (default)" : ""}</option>)}
              </Select>
            )}
          </Field>
          </WithAdd>
          <Field label="Delivery receipt / invoice no." optional error={fields.deliveryRef}>{(p) => <Input {...p} value={deliveryRef} onChange={(e) => setDeliveryRef(e.target.value)} />}</Field>
        </div>
      </Sheet>

      <Sheet className="px-5 pt-4 pb-4 sm:px-6">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[60rem] text-left text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-meta text-ink-3">
                <th className="py-2 pr-3 font-semibold">Product</th>
                <th className="w-24 px-2 py-2 text-right font-semibold">Received</th>
                <th className="w-28 px-2 py-2 text-right font-semibold">Unit cost</th>
                <th className="px-2 py-2 font-semibold">Batch / lot</th>
                <th className="px-2 py-2 font-semibold">Made</th>
                <th className="px-2 py-2 font-semibold">Expires</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {rows.map((r, i) => {
                const p = byId.get(r.productId);
                const err = fields[`lines.${i}.productId`] || fields[`lines.${i}.quantity`];
                return (
                  <tr key={i}>
                    <td className="py-2 pr-3 align-top">
                      {r.orderLineId ? (
                        <span className="font-semibold">{p?.name}<span className="block text-meta font-normal text-ink-3">{p?.sku} · {r.outstanding} still owed</span></span>
                      ) : (
                        <Select aria-label={`Line ${i + 1} product`} value={r.productId} onChange={(e) => set(i, { productId: e.target.value })} className="w-full">
                          <option value="">Pick a product…</option>
                          {products.filter((x) => x.status !== "discontinued").map((x) => <option key={x.id} value={x.id}>{x.name} · {x.sku}</option>)}
                        </Select>
                      )}
                      {p?.trackSerials && (
                        <Textarea aria-label={`Line ${i + 1} serial numbers`} rows={2} placeholder={`${Number(r.quantity) || 0} serial numbers, one per unit`} value={r.serials} onChange={(e) => set(i, { serials: e.target.value })} className="mt-2 !min-h-14 font-mono text-meta" />
                      )}
                      {err && <p className="mt-1 text-meta text-danger">{err}</p>}
                    </td>
                    <td className="px-2 py-2 align-top">
                      <CellInput aria-label={`Line ${i + 1} quantity`} inputMode="numeric" value={r.quantity} onChange={(e) => set(i, { quantity: e.target.value.replace(/\D/g, "") })} className="w-20" />
                    </td>
                    <td className="px-2 py-2 align-top">
                      <CellInput aria-label={`Line ${i + 1} unit cost`} inputMode="decimal" value={r.cost} onChange={(e) => set(i, { cost: e.target.value })} className="w-24" />
                    </td>
                    <td className="px-2 py-2 align-top">
                      {p?.trackBatches ? <input aria-label={`Line ${i + 1} batch`} value={r.batchNo} onChange={(e) => set(i, { batchNo: e.target.value })} className={`${cell} w-32 font-mono`} /> : <span className="text-meta text-ink-3">—</span>}
                    </td>
                    <td className="px-2 py-2 align-top">
                      {p?.trackBatches ? <input type="date" aria-label={`Line ${i + 1} made on`} value={r.manufacturedOn} onChange={(e) => set(i, { manufacturedOn: e.target.value })} className={cell} /> : null}
                    </td>
                    <td className="px-2 py-2 align-top">
                      {p?.trackExpiry ? <input type="date" aria-label={`Line ${i + 1} expires on`} value={r.expiresOn} onChange={(e) => set(i, { expiresOn: e.target.value })} className={cell} /> : null}
                    </td>
                    <td className="py-2 text-right align-top">
                      {rows.length > 1 && (
                        <button type="button" title="Remove this line" onClick={() => setRows(rows.filter((_, j) => j !== i))} className="rounded-md p-1.5 text-ink-3 hover:bg-bench hover:text-danger">
                          <X className="size-4" aria-hidden />
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {!order && (
          <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1">
            <Button size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => setRows([...rows, blank()])}>
              Add a line
            </Button>
            {canAdd.product && <QuickAdd kind="product" label="New product (not in the list)" context={{ org, units: reference.units.filter((u) => u.isActive) }} onAdded={productAdded} />}
          </div>
        )}
        {order && <p className="mt-2 text-meta text-ink-3">Received less than what&apos;s owed? Put what came: the rest stays on backorder.</p>}
      </Sheet>
      <Field label="Notes" optional error={fields.notes}>{(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
      <FormError message={error ?? fields.lines} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>Receive into stock</Button>
        <LinkButton href={order ? `/purchase-orders/${order.id}` : "/receipts"} variant="quiet">Cancel</LinkButton>
      </div>
    </form>
  );
}
