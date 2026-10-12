"use client";

import { useState } from "react";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { saveOrder, savePurchaseOrder, saveTransfer } from "../actions/inventory";
import { kindOf } from "../lib/order-kinds";
import type { Order, OrderKind, PO, Reference, Transfer } from "../lib/types";
import { blankLine, LinesEditor, linesOut, useSave, type Line } from "./lines";
import { QuickAdd, WithAdd, withAdded, type Added, type CanAdd } from "./quick-add";

/** Things added from this form, listed until the page's own lists have them. */
function useAdded() {
  const [added, setAdded] = useState<Added[]>([]);
  return { added, remember: (a: Added) => setAdded((list) => [...list, a]) };
}

const asOption = (a: Added) => ({ value: a.value, label: a.label });
const options = (list: { value: string; label: string }[]) => list.map((o) => <option key={o.value} value={o.value}>{o.label}</option>);

// The three documents made of product lines: purchase orders, orders, transfers.

const active = <T extends { isActive: boolean }>(items: T[], keep?: string, id: (t: T) => string = (t) => (t as unknown as { id: string }).id) =>
  items.filter((t) => t.isActive || id(t) === keep);

export function PurchaseOrderForm({ org, reference, order, preset, canAdd = {} }: {
  org: Org;
  canAdd?: CanAdd;
  reference: Pick<Reference, "products" | "suppliers" | "units" | "warehouses">;
  order?: PO;
  preset?: { supplierId?: string; productId?: string; quantity?: string };
}) {
  const fmt = makeFormat(org);
  const { pending, error, fields, save } = useSave();
  const [supplierId, setSupplierId] = useState(order?.supplier.id ?? preset?.supplierId ?? "");
  const [warehouseId, setWarehouseId] = useState(order?.warehouse.id ?? reference.warehouses.find((w) => w.isActive)?.id ?? "");
  const [expectedOn, setExpectedOn] = useState(order?.expectedOn ?? "");
  const [notes, setNotes] = useState(order?.notes ?? "");
  const [lines, setLines] = useState<Line[]>(() => {
    if (order) return order.lines.map((l) => ({ productId: l.product.id, quantity: String(l.quantity), money: fmt.pesosText(l.unitCost) }));
    const p = reference.products.find((x) => x.id === preset?.productId);
    return p ? [{ productId: p.id, quantity: preset?.quantity ?? "", money: fmt.pesosText(p.costPrice) }] : [blankLine()];
  });
  const { added, remember } = useAdded();
  const supplierOptions = withAdded(active(reference.suppliers, supplierId).map((x) => ({ value: x.id, label: x.name })), added, "supplier", asOption);
  const warehouseOptions = withAdded(active(reference.warehouses, warehouseId).map((w) => ({ value: w.id, label: w.name })), added, "warehouse", asOption);
  // Suggest the chosen supplier's own products first.
  const products = [...reference.products].sort((a, b) => Number(b.supplierId === supplierId) - Number(a.supplierId === supplierId));

  function submit() {
    const input = { supplierId, warehouseId, expectedOn: expectedOn || null, notes: notes.trim() || null, lines: linesOut(lines, fmt, "unitCost") };
    save(() => savePurchaseOrder(order?.id ?? null, input), (out) => ({ message: order ? "Purchase order saved" : "Purchase order drafted", go: `/purchase-orders/${order?.id ?? out.id}` }));
  }

  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); submit(); }} className="space-y-5">
      <Sheet className="px-5 pt-4 pb-5 sm:px-6">
        <div className="grid gap-5 sm:grid-cols-3">
          <WithAdd can={canAdd.supplier} add={<QuickAdd kind="supplier" label="New" onAdded={(a) => { remember(a); setSupplierId(a.value); }} />}>
            <Field label="Supplier" error={fields.supplierId}>
              {(p) => (
                <Select {...p} value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
                  <option value="">Pick a supplier…</option>
                  {options(supplierOptions)}
                </Select>
              )}
            </Field>
          </WithAdd>
          <WithAdd can={canAdd.warehouse} add={<QuickAdd kind="warehouse" label="New" onAdded={(a) => { remember(a); setWarehouseId(a.value); }} />}>
            <Field label="Deliver to" error={fields.warehouseId}>
              {(p) => (
                <Select {...p} value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
                  {options(warehouseOptions)}
                </Select>
              )}
            </Field>
          </WithAdd>
          <Field label="Expected on" optional error={fields.expectedOn}>
            {(p) => <Input {...p} type="date" value={expectedOn} onChange={(e) => setExpectedOn(e.target.value)} />}
          </Field>
        </div>
      </Sheet>
      <Sheet className="px-5 pt-4 pb-4 sm:px-6">
        <LinesEditor products={products} lines={lines} onChange={setLines} errors={fields} fmt={fmt} money={{ label: `Unit cost (${fmt.symbol})`, from: "costPrice" }} addProduct={canAdd.product ? { org, units: reference.units.filter((u) => u.isActive) } : undefined} />
      </Sheet>
      <Field label="Notes" optional error={fields.notes}>{(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
      <FormError message={error ?? fields.lines} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>{order ? "Save draft" : "Save as draft"}</Button>
        <LinkButton href={order ? `/purchase-orders/${order.id}` : "/purchase-orders"} variant="quiet">Cancel</LinkButton>
      </div>
      <p className="text-meta text-ink-3">A draft is placed with the supplier by someone who may approve purchase orders. Until then it can still change.</p>
    </form>
  );
}

export function OrderForm({ org, reference, order, available, kind: given, canAdd = {} }: {
  org: Org;
  /** Which kind of order this form is for (each has its own page); an order being edited keeps its own. */
  kind: OrderKind;
  canAdd?: CanAdd;
  reference: Pick<Reference, "products" | "units" | "warehouses">;
  order?: Order;
  /** What's free per product, per warehouse: "productId:warehouseId" → units. */
  available: Record<string, number>;
}) {
  const fmt = makeFormat(org);
  const { pending, error, fields, save } = useSave();
  const kind = order?.kind ?? given;
  const info = kindOf(kind)!;
  const [recipient, setRecipient] = useState(order?.recipient ?? "");
  const [warehouseId, setWarehouseId] = useState(order?.warehouse.id ?? reference.warehouses.find((w) => w.isActive)?.id ?? "");
  const [neededOn, setNeededOn] = useState(order?.neededOn ?? "");
  const [notes, setNotes] = useState(order?.notes ?? "");
  const [lines, setLines] = useState<Line[]>(() => order?.lines.map((l) => ({ productId: l.product.id, quantity: String(l.quantity), money: fmt.pesosText(l.unitPrice) })) ?? [blankLine()]);
  const sale = info.priced;
  const { added, remember } = useAdded();
  const warehouseOptions = withAdded(active(reference.warehouses, warehouseId).map((w) => ({ value: w.id, label: w.name })), added, "warehouse", asOption);

  function submit() {
    const input = { kind, recipient: recipient.trim(), warehouseId, neededOn: neededOn || null, notes: notes.trim() || null, lines: linesOut(lines, fmt, "unitPrice") };
    save(() => saveOrder(order?.id ?? null, input), (out) => ({ message: order ? `${info.one.charAt(0).toUpperCase()}${info.one.slice(1)} saved` : `${info.one.charAt(0).toUpperCase()}${info.one.slice(1)} written up`, go: `/orders/${order?.id ?? out.id}` }));
  }

  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); submit(); }} className="space-y-5">
      <Sheet className="px-5 pt-4 pb-5 sm:px-6">
        <div className="grid gap-5 sm:grid-cols-3">
          <Field label={info.recipient.label} hint={info.recipient.hint} error={fields.recipient}>
            {(p) => <Input {...p} value={recipient} placeholder={info.recipient.placeholder} onChange={(e) => setRecipient(e.target.value)} autoFocus={!order} />}
          </Field>
          <WithAdd can={canAdd.warehouse} add={<QuickAdd kind="warehouse" label="New" onAdded={(a) => { remember(a); setWarehouseId(a.value); }} />}>
            <Field label="From warehouse" error={fields.warehouseId}>
              {(p) => (
                <Select {...p} value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
                  {options(warehouseOptions)}
                </Select>
              )}
            </Field>
          </WithAdd>
          <Field label="Needed by" optional error={fields.neededOn}>{(p) => <Input {...p} type="date" value={neededOn} onChange={(e) => setNeededOn(e.target.value)} />}</Field>
        </div>
      </Sheet>
      <Sheet className="px-5 pt-4 pb-4 sm:px-6">
        <LinesEditor
          products={reference.products}
          lines={lines}
          onChange={setLines}
          errors={fields}
          fmt={fmt}
          money={sale ? { label: `Unit price (${fmt.symbol})`, from: "sellingPrice" } : undefined}
          note={(id) => `${fmt.count(available[`${id}:${warehouseId}`] ?? 0)} available in this warehouse`}
          limit={(id) => available[`${id}:${warehouseId}`] ?? 0}
          addProduct={canAdd.product ? { org, units: reference.units.filter((u) => u.isActive) } : undefined}
        />
      </Sheet>
      <Field label={info.notes.label} hint={info.notes.hint} optional error={fields.notes}>{(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
      <FormError message={error ?? fields.lines} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>{order ? "Save" : "Save as draft"}</Button>
        <LinkButton href={order ? `/orders/${order.id}` : "/orders"} variant="quiet">Cancel</LinkButton>
      </div>
      <p className="text-meta text-ink-3">Confirming the order reserves its stock, so nothing else can take it. Then it&apos;s picked and issued.</p>
    </form>
  );
}

export function TransferForm({ org, reference, transfer, available, canAdd = {} }: { org: Org; reference: Pick<Reference, "products" | "warehouses">; transfer?: Transfer; available: Record<string, number>; canAdd?: CanAdd }) {
  const fmt = makeFormat(org);
  const { pending, error, fields, save } = useSave();
  const { added, remember } = useAdded();
  const warehouses = withAdded(active(reference.warehouses).map((w) => ({ value: w.id, label: w.name })), added, "warehouse", asOption);
  const [from, setFrom] = useState(transfer?.from.id ?? warehouses[0]?.value ?? "");
  const [to, setTo] = useState(transfer?.to.id ?? warehouses[1]?.value ?? "");
  const [notes, setNotes] = useState(transfer?.notes ?? "");
  const [lines, setLines] = useState<Line[]>(() => transfer?.lines.map((l) => ({ productId: l.product.id, quantity: String(l.quantity), money: "" })) ?? [blankLine()]);

  function submit(request: boolean) {
    const input = { fromWarehouseId: from, toWarehouseId: to, notes: notes.trim() || null, lines: linesOut(lines, fmt), request };
    save(() => saveTransfer(transfer?.id ?? null, input), (out) => ({ message: transfer ? "Transfer saved" : request ? "Transfer requested" : "Transfer drafted", go: `/transfers/${transfer?.id ?? out.id}` }));
  }

  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); submit(!transfer); }} className="space-y-5">
      <Sheet className="px-5 pt-4 pb-5 sm:px-6">
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="From" error={fields.fromWarehouseId}>
            {(p) => <Select {...p} value={from} onChange={(e) => { const next = e.target.value; setFrom(next); /* From and To can't be one warehouse: To moves to the next one. */ if (next === to) setTo(warehouses.find((w) => w.value !== next)?.value ?? ""); }}>{options(warehouses)}</Select>}
          </Field>
          <WithAdd can={canAdd.warehouse} add={<QuickAdd kind="warehouse" label="New" onAdded={(a) => { remember(a); setTo(a.value); }} />}>
            <Field label="To" error={fields.toWarehouseId}>
              {(p) => <Select {...p} value={to} onChange={(e) => setTo(e.target.value)}>{warehouses.map((w) => <option key={w.value} value={w.value} disabled={w.value === from}>{w.label}</option>)}</Select>}
            </Field>
          </WithAdd>
        </div>
      </Sheet>
      <Sheet className="px-5 pt-4 pb-4 sm:px-6">
        <LinesEditor products={reference.products} lines={lines} onChange={setLines} errors={fields} fmt={fmt} note={(id) => `${fmt.count(available[`${id}:${from}`] ?? 0)} available to send`} limit={(id) => available[`${id}:${from}`] ?? 0} />
      </Sheet>
      <Field label="Notes" optional error={fields.notes}>{(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
      <FormError message={error ?? fields.lines} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending}>{transfer ? "Save" : "Request transfer"}</Button>
        {!transfer && <Button loading={pending} onClick={() => submit(false)}>Save as draft</Button>}
        <LinkButton href={transfer ? `/transfers/${transfer.id}` : "/transfers"} variant="quiet">Cancel</LinkButton>
      </div>
    </form>
  );
}
