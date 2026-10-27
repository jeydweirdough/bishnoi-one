"use client";

import { useState, type ReactNode } from "react";
import { Button, LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { Field, FormError, FormGrid, Input, Select, Textarea } from "@/src/modules/inventory/platform/ui/field";
import { Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import { makeFormat } from "@/src/modules/inventory/platform/lib/format";
import type { Org } from "@/src/modules/inventory/platform/lib/types";
import { saveOrder, savePurchaseOrder, saveTransfer } from "@/src/modules/inventory/actions/inventory";
import { kindOf } from "@/src/modules/inventory/lib/order-kinds";
import type { Order, OrderKind, PO, Reference, Transfer } from "@/src/modules/inventory/lib/types";
import { blankLine, LinesEditor, linesOut, useSave, type Line } from "@/src/modules/inventory/components/lines";
import { QuickAdd, WithAdd, withAdded, type Added, type CanAdd } from "@/src/modules/inventory/components/quick-add";

/** Things added from this form, listed until the page's own lists have them. */
function useAdded() {
  const [added, setAdded] = useState<Added[]>([]);
  return { added, remember: (a: Added) => setAdded((list) => [...list, a]) };
}

const asOption = (a: Added) => ({ value: a.value, label: a.label });
const options = (list: { value: string; label: string }[]) => list.map((o) => <option key={o.value} value={o.value}>{o.label}</option>);

// The three documents made of product lines: purchase orders, orders, transfers.
// Each is laid out the same way: its details and its items on the left, and on
// the right a summary (lines, quantity, total) with what to do, kept in view.

/** The document's figures, worked out from its lines as they're typed. */
function figures(lines: Line[], fmt: ReturnType<typeof makeFormat>, priced: boolean) {
  const used = lines.filter((l) => l.productId);
  return {
    lines: used.length,
    quantity: used.reduce((n, l) => n + (Number(l.quantity) || 0), 0),
    total: priced ? used.reduce((n, l) => n + (Number(l.quantity) || 0) * (fmt.toCentavos(l.money) ?? 0), 0) : null,
  };
}

function DocumentLayout({ details, items, summary }: { details: ReactNode; items: ReactNode; summary: ReactNode }) {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem] xl:items-start">
      <div className="min-w-0 space-y-5">
        {details}
        {items}
      </div>
      <aside className="xl:sticky xl:top-4">{summary}</aside>
    </div>
  );
}

function Summary({ fmt, counts, error, children, note }: { fmt: ReturnType<typeof makeFormat>; counts: ReturnType<typeof figures>; error?: string | null; children: ReactNode; note?: string }) {
  return (
    <Sheet className="px-5 pt-4 pb-5">
      <h2 className="text-heading text-ink">Summary</h2>
      <dl className="mt-3 space-y-2 text-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-ink-2">Lines</dt>
          <dd className="font-medium text-ink tabular-nums">{counts.lines}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-ink-2">Total quantity</dt>
          <dd className="font-medium text-ink tabular-nums">{fmt.count(counts.quantity)}</dd>
        </div>
        {counts.total !== null && (
          <div className="flex justify-between gap-3 border-t border-rule pt-2">
            <dt className="font-semibold text-ink">Total</dt>
            <dd className="text-lg font-semibold text-ink tabular-nums">{fmt.peso(counts.total)}</dd>
          </div>
        )}
      </dl>
      <div className="mt-4">
        <FormError message={error} />
      </div>
      <div className="mt-3 flex flex-col gap-2">{children}</div>
      {note && <p className="mt-3 text-meta text-ink-3">{note}</p>}
    </Sheet>
  );
}

const Heading = ({ children }: { children: ReactNode }) => <h2 className="mb-4 text-heading text-ink">{children}</h2>;

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
  const { pending, error, fields, save, shakeClass, anticipateClass } = useSave();
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
    save(() => savePurchaseOrder(order?.id ?? null, input), (out) => ({ message: order ? "Purchase order saved" : "Purchase order saved as draft", go: `/inventory/purchase-orders/${order?.id ?? out.id}` }));
  }

  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); submit(); }} className={`rounded-xl transition-all duration-300 ${shakeClass} ${anticipateClass}`}>
      <DocumentLayout
        details={
          <Sheet className="px-5 pt-4 pb-5 sm:px-6">
            <Heading>Details</Heading>
            <div className="grid gap-5 sm:grid-cols-3">
              <WithAdd can={canAdd.supplier} add={<QuickAdd kind="supplier" label="New" onAdded={(a) => { remember(a); setSupplierId(a.value); }} />}>
                <Field label="Vendor" error={fields.supplierId}>
                  {(p) => (
                    <Select {...p} value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
                      <option value="">Select a vendor</option>
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
              <Field label="Expected delivery date" optional error={fields.expectedOn}>
                {(p) => <Input {...p} type="date" value={expectedOn} onChange={(e) => setExpectedOn(e.target.value)} />}
              </Field>
            </div>
            <div className="mt-5">
              <Field label="Notes" optional hint="For the vendor or the people receiving it." error={fields.notes}>{(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
            </div>
          </Sheet>
        }
        items={
          <Sheet className="px-5 pt-4 pb-4 sm:px-6">
            <Heading>Items</Heading>
            <LinesEditor products={products} lines={lines} onChange={setLines} errors={fields} fmt={fmt} money={{ label: "Unit cost", from: "costPrice" }} addProduct={canAdd.product ? { org, units: reference.units.filter((u) => u.isActive) } : undefined} />
          </Sheet>
        }
        summary={
          <Summary fmt={fmt} counts={figures(lines, fmt, true)} error={error ?? fields.lines} note="A draft can be edited until an approver places the order with the vendor.">
            <Button type="submit" variant="primary" loading={pending} className="w-full">{order ? "Save draft" : "Save as draft"}</Button>
            <LinkButton href={order ? `/inventory/purchase-orders/${order.id}` : "/inventory/purchase-orders"} variant="quiet" className="w-full">Cancel</LinkButton>
          </Summary>
        }
      />
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
  const { pending, error, fields, save, shakeClass, anticipateClass } = useSave();
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
    save(() => saveOrder(order?.id ?? null, input), (out) => ({ message: order ? `${info.one.charAt(0).toUpperCase()}${info.one.slice(1)} saved` : `${info.one.charAt(0).toUpperCase()}${info.one.slice(1)} created`, go: `/inventory/orders/${order?.id ?? out.id}` }));
  }

  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); submit(); }} className={`rounded-xl transition-all duration-300 ${shakeClass} ${anticipateClass}`}>
      <DocumentLayout
        details={
          <Sheet className="px-5 pt-4 pb-5 sm:px-6">
            <Heading>Details</Heading>
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
              <Field label="Required date" optional error={fields.neededOn}>{(p) => <Input {...p} type="date" value={neededOn} onChange={(e) => setNeededOn(e.target.value)} />}</Field>
            </div>
            <div className="mt-5">
              <Field label={info.notes.label} hint={info.notes.hint} optional error={fields.notes}>{(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
            </div>
          </Sheet>
        }
        items={
          <Sheet className="px-5 pt-4 pb-4 sm:px-6">
            <Heading>Items</Heading>
            <LinesEditor
              products={reference.products}
              lines={lines}
              onChange={setLines}
              errors={fields}
              fmt={fmt}
              money={sale ? { label: "Unit price", from: "sellingPrice" } : undefined}
              note={(id) => `${fmt.count(available[`${id}:${warehouseId}`] ?? 0)} available in this warehouse`}
              limit={(id) => available[`${id}:${warehouseId}`] ?? 0}
              addProduct={canAdd.product ? { org, units: reference.units.filter((u) => u.isActive) } : undefined}
            />
          </Sheet>
        }
        summary={
          <Summary fmt={fmt} counts={figures(lines, fmt, Boolean(sale))} error={error ?? fields.lines} note="Confirming the order reserves its stock. The order is then picked and issued.">
            <Button type="submit" variant="primary" loading={pending} className="w-full">{order ? "Save" : "Save as draft"}</Button>
            <LinkButton href={order ? `/inventory/orders/${order.id}` : "/inventory/orders"} variant="quiet" className="w-full">Cancel</LinkButton>
          </Summary>
        }
      />
    </form>
  );
}

export function TransferForm({ org, reference, transfer, available, canAdd = {} }: { org: Org; reference: Pick<Reference, "products" | "warehouses">; transfer?: Transfer; available: Record<string, number>; canAdd?: CanAdd }) {
  const fmt = makeFormat(org);
  const { pending, error, fields, save, shakeClass, anticipateClass } = useSave();
  const { added, remember } = useAdded();
  const warehouses = withAdded(active(reference.warehouses).map((w) => ({ value: w.id, label: w.name })), added, "warehouse", asOption);
  const [from, setFrom] = useState(transfer?.from.id ?? warehouses[0]?.value ?? "");
  const [to, setTo] = useState(transfer?.to.id ?? warehouses[1]?.value ?? "");
  const [notes, setNotes] = useState(transfer?.notes ?? "");
  const [lines, setLines] = useState<Line[]>(() => transfer?.lines.map((l) => ({ productId: l.product.id, quantity: String(l.quantity), money: "" })) ?? [blankLine()]);

  function submit(request: boolean) {
    const input = { fromWarehouseId: from, toWarehouseId: to, notes: notes.trim() || null, lines: linesOut(lines, fmt), request };
    save(() => saveTransfer(transfer?.id ?? null, input), (out) => ({ message: transfer ? "Transfer saved" : request ? "Transfer requested" : "Transfer saved as draft", go: `/inventory/transfers/${transfer?.id ?? out.id}` }));
  }

  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); submit(!transfer); }} className={`rounded-xl transition-all duration-300 ${shakeClass} ${anticipateClass}`}>
      <DocumentLayout
        details={
          <Sheet className="px-5 pt-4 pb-5 sm:px-6">
            <Heading>Details</Heading>
            <FormGrid>
              <Field label="Source warehouse" size="md" error={fields.fromWarehouseId}>
                {(p) => <Select {...p} value={from} onChange={(e) => { const next = e.target.value; setFrom(next); /* From and To can't be one warehouse: To moves to the next one. */ if (next === to) setTo(warehouses.find((w) => w.value !== next)?.value ?? ""); }}>{options(warehouses)}</Select>}
              </Field>
              <WithAdd can={canAdd.warehouse} className="sm:col-span-3" add={<QuickAdd kind="warehouse" label="New" onAdded={(a) => { remember(a); setTo(a.value); }} />}>
                <Field label="Destination warehouse" size="md" error={fields.toWarehouseId}>
                  {(p) => <Select {...p} value={to} onChange={(e) => setTo(e.target.value)}>{warehouses.map((w) => <option key={w.value} value={w.value} disabled={w.value === from}>{w.label}</option>)}</Select>}
                </Field>
              </WithAdd>
            </FormGrid>
            <div className="mt-5">
              <Field label="Notes" optional error={fields.notes}>{(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
            </div>
          </Sheet>
        }
        items={
          <Sheet className="px-5 pt-4 pb-4 sm:px-6">
            <Heading>Items</Heading>
            <LinesEditor products={reference.products} lines={lines} onChange={setLines} errors={fields} fmt={fmt} note={(id) => `${fmt.count(available[`${id}:${from}`] ?? 0)} available to send`} limit={(id) => available[`${id}:${from}`] ?? 0} />
          </Sheet>
        }
        summary={
          <Summary fmt={fmt} counts={figures(lines, fmt, false)} error={error ?? fields.lines} note="A requested transfer goes to an approver; the source warehouse then sends it.">
            <Button type="submit" variant="primary" loading={pending} className="w-full">{transfer ? "Save" : "Request transfer"}</Button>
            {!transfer && <Button loading={pending} onClick={() => submit(false)} className="w-full">Save as draft</Button>}
            <LinkButton href={transfer ? `/inventory/transfers/${transfer.id}` : "/inventory/transfers"} variant="quiet" className="w-full">Cancel</LinkButton>
          </Summary>
        }
      />
    </form>
  );
}
