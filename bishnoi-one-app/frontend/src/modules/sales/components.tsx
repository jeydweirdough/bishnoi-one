"use client";

import { Modal } from "antd";
import { Check, Send, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { LinesEditor, blankLine, linesOut, useSave, type Line } from "@/src/modules/inventory/components/lines";
import { makeFormat } from "@/src/modules/inventory/platform/lib/format";
import type { Org } from "@/src/modules/inventory/platform/lib/types";
import type { Reference } from "@/src/modules/inventory/lib/types";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import { rejectSalesOrder, saveSalesOrder, salesOrderStep } from "./actions";
import type { SalesOrder } from "./types";

// The Sales app's controls (feature plan step 11): the order's steps beside its title, and the form for an order taken here.

/** Submit, approve or reject, and cancel: each where it applies, for whoever may. */
export function SalesOrderSteps({ order, may }: { order: SalesOrder; may: { create: boolean; edit: boolean; approve: boolean } }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");

  function run(step: "submit" | "approve" | "cancel", done: string) {
    start(async () => {
      const r = await salesOrderStep(order.id, step);
      if (!r.ok) return void toast.error(r.error);
      toast.success(done);
      router.refresh();
    });
  }

  function reject() {
    start(async () => {
      const r = await rejectSalesOrder(order.id, note.trim());
      if (!r.ok) return void toast.error(r.error);
      toast.success("Order rejected", { description: order.quote ? "The rep sees your reason on the quote." : "Its maker can change it and send it again." });
      setRejecting(false);
      router.refresh();
    });
  }

  const open = !["delivered", "cancelled"].includes(order.status) && !order.deliveries.some((d) => d.status !== "draft" && d.status !== "cancelled");
  return (
    <div className="flex flex-wrap gap-2">
      {(order.status === "draft" || (order.status === "rejected" && !order.quote)) && may.create && (
        <Button variant="primary" icon={<Send className="size-4" aria-hidden />} loading={busy} onClick={() => run("submit", "Sent for approval")}>
          Send for approval
        </Button>
      )}
      {order.status === "pending" && may.approve && (
        <>
          <Button variant="primary" icon={<Check className="size-4" aria-hidden />} loading={busy} onClick={() => run("approve", "Approved: its delivery is made for the warehouse")}>
            Approve
          </Button>
          <Button icon={<X className="size-4" aria-hidden />} disabled={busy} onClick={() => setRejecting(true)}>
            Reject
          </Button>
        </>
      )}
      {open && may.edit && order.status !== "rejected" && (
        <Button variant="quiet" disabled={busy} onClick={() => run("cancel", "Order cancelled")}>
          Cancel order
        </Button>
      )}
      <Modal open={rejecting} title={`Reject ${order.number}?`} onCancel={() => !busy && setRejecting(false)} onOk={reject} okText="Reject" okButtonProps={{ danger: true, disabled: note.trim().length < 3 }} confirmLoading={busy} destroyOnHidden>
        <Field label="Why" hint={order.quote ? "The rep sees it on the quote." : "Its maker sees it on the order."}>
          {(p) => <Textarea {...p} rows={3} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} autoFocus />}
        </Field>
      </Modal>
    </div>
  );
}

/** An order taken here (by phone or in person): the customer, the warehouse, the lines at the price list's prices. */
export function SalesOrderForm({ org, reference }: { org: Org; reference: Pick<Reference, "products" | "warehouses"> }) {
  const fmt = makeFormat(org);
  const { pending, error, fields, save, shakeClass } = useSave();
  const warehouses = reference.warehouses.filter((w) => w.isActive);
  const [form, setForm] = useState({ customerName: "", customerAddress: "", customerTin: "", warehouseId: warehouses[0]?.id ?? "", scheduledOn: "", notes: "" });
  const [lines, setLines] = useState<Line[]>([blankLine()]);
  const prices = Object.fromEntries(reference.products.map((p) => [p.id, p.sellingPrice]));
  const total = lines.reduce((n, l) => n + (prices[l.productId] ?? 0) * (Number(l.quantity) || 0), 0);

  function submit() {
    const input = {
      customerName: form.customerName.trim(), customerAddress: form.customerAddress.trim() || null, customerTin: form.customerTin.trim() || null,
      warehouseId: form.warehouseId || null, scheduledOn: form.scheduledOn || null, notes: form.notes.trim() || null,
      lines: linesOut(lines, fmt).map(({ productId, quantity }) => ({ productId, quantity })),
    };
    save(() => saveSalesOrder(null, input), (out) => ({ message: "Sales order saved as a draft", go: `/sales/orders/${out.id}` }));
  }

  return (
    <form noValidate onSubmit={(e) => (e.preventDefault(), submit())} className={`space-y-5 ${shakeClass}`}>
      <Sheet className="px-5 pt-4 pb-5">
        <div className="grid gap-5 sm:grid-cols-3">
          <Field label="Customer" error={fields.customerName}>{(p) => <Input {...p} value={form.customerName} onChange={(e) => setForm({ ...form, customerName: e.target.value })} maxLength={200} autoFocus />}</Field>
          <Field label="Address" optional error={fields.customerAddress}>{(p) => <Input {...p} value={form.customerAddress} onChange={(e) => setForm({ ...form, customerAddress: e.target.value })} maxLength={400} />}</Field>
          <Field label="TIN" optional error={fields.customerTin}>{(p) => <Input {...p} value={form.customerTin} onChange={(e) => setForm({ ...form, customerTin: e.target.value })} maxLength={30} />}</Field>
          <Field label="Ships from" error={fields.warehouseId}>
            {(p) => (
              <Select {...p} value={form.warehouseId} onChange={(e) => setForm({ ...form, warehouseId: e.target.value })}>
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Scheduled date" optional error={fields.scheduledOn}>{(p) => <Input {...p} type="date" value={form.scheduledOn} onChange={(e) => setForm({ ...form, scheduledOn: e.target.value })} />}</Field>
        </div>
        <div className="mt-5">
          <Field label="Notes" optional error={fields.notes}>{(p) => <Textarea {...p} rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />}</Field>
        </div>
      </Sheet>
      <Sheet className="px-5 pt-4 pb-4">
        <LinesEditor
          products={reference.products}
          lines={lines}
          onChange={setLines}
          errors={fields}
          fmt={fmt}
          note={(id) => (prices[id] !== undefined ? `${fmt.peso(prices[id])} each, from the price list` : null)}
        />
        <p className="mt-3 text-right text-sm text-ink-2">
          Total <strong className="text-ink">{fmt.peso(total)}</strong>
        </p>
      </Sheet>
      <FormError message={error ?? fields.lines} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          Save as draft
        </Button>
      </div>
    </form>
  );
}
