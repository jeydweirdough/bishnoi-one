"use client";

import { Checkbox, Modal } from "antd";
import { Check, ExternalLink, Pencil, RotateCcw, Truck, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { markDelivered, markFailed, saveCourier, sendAgain, setShipping } from "@/src/modules/inventory/actions/inventory";
import type { Courier, DeliveryMethod, Shipping } from "@/src/modules/inventory/lib/types";
import { Button } from "@/src/platform/ui/button";
import { Choice, Field, FileInput, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { Empty } from "@/src/platform/ui/sheet";

// Shipping with couriers (feature plan step 12): how a delivery goes (courier, our delivery, pick-up), the
// courier's tracking number and fee; once issued, out for delivery, then delivered or failed. Proof of
// delivery is the customer's signature on screen (step 10) or the courier's photo.

const METHODS: { value: DeliveryMethod; label: string }[] = [
  { value: "courier", label: "Courier" },
  { value: "own", label: "Our delivery" },
  { value: "pickup", label: "Customer pick-up" },
];

const TONE: Record<string, string> = { out: "border-due-today text-due-today", delivered: "border-sage-deep text-sage-deep", failed: "border-danger text-danger" };

const pesos = (centavos: number) => (centavos / 100).toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function readFile(file: File): Promise<string> {
  return new Promise((done, fail) => {
    const r = new FileReader();
    r.onload = () => done(String(r.result));
    r.onerror = () => fail(r.error);
    r.readAsDataURL(file);
  });
}

/** The delivery's shipping, with its steps: set how it goes, then delivered, failed or sent again. */
export function ShippingCard({ orderId, issued, shipping, couriers, may, signedFor }: {
  orderId: string;
  issued: boolean;
  shipping: Shipping;
  couriers: Courier[];
  may: { edit: boolean; issue: boolean };
  /** Signed for on screen already (step 10): delivered by that. */
  signedFor: boolean;
}) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [open, setOpen] = useState<"edit" | "delivered" | "failed" | null>(null);
  const [form, setForm] = useState({
    method: (shipping.method ?? "courier") as DeliveryMethod, courierId: shipping.courier?.id ?? "", trackingNumber: shipping.trackingNumber ?? "",
    fee: shipping.fee ? String(shipping.fee / 100) : "", feeCharged: shipping.feeCharged,
  });
  const [receivedBy, setReceivedBy] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [reason, setReason] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const delivered = shipping.status === "delivered";
  const mayChange = !delivered && (issued ? may.issue : may.edit);
  const active = couriers.filter((c) => c.isActive || c.id === shipping.courier?.id);

  function done(message: string, description?: string) {
    toast.success(message, description ? { description } : undefined);
    setOpen(null);
    setFields({});
    setError(null);
    router.refresh();
  }

  function fail(r: { error: string; fields?: Record<string, string> }) {
    setFields(r.fields ?? {});
    setError(r.fields ? null : r.error);
  }

  function save() {
    const fee = Math.round((Number(form.fee.replace(/,/g, "")) || 0) * 100);
    start(async () => {
      const r = await setShipping(orderId, {
        method: form.method, courierId: form.method === "courier" ? form.courierId || null : null,
        trackingNumber: form.method === "courier" ? form.trackingNumber.trim() || null : null, fee, feeCharged: form.feeCharged && fee > 0,
      });
      if (!r.ok) return fail(r);
      done("Shipping saved");
    });
  }

  function deliver() {
    if (receivedBy.trim().length < 2) return setFields({ receivedBy: "Who received it, as the courier reports." });
    start(async () => {
      const r = await markDelivered(orderId, receivedBy.trim(), photo ? await readFile(photo) : null);
      if (!r.ok) return fail(r);
      done("Delivered", photo ? "The courier's photo is kept as proof of delivery." : undefined);
    });
  }

  function failed() {
    start(async () => {
      const r = await markFailed(orderId, reason.trim());
      if (!r.ok) return fail(r);
      done("Marked as a failed delivery", "Send it again when it goes out next.");
    });
  }

  function again() {
    start(async () => {
      const r = await sendAgain(orderId);
      if (!r.ok) return void toast.error(r.error);
      done("Out for delivery again");
    });
  }

  const set = !!shipping.method;
  return (
    <div>
      <div className="flex flex-wrap items-start gap-x-6 gap-y-2">
        <div className="min-w-0 flex-1">
          <p className="text-caps text-ink-3 uppercase">Shipping</p>
          {set ? (
            <p className="text-sm text-ink">
              <strong>{shipping.method === "courier" ? (shipping.courier?.name ?? "Courier not chosen") : shipping.methodLabel}</strong>
              {shipping.trackingNumber && (
                <>
                  {" · "}
                  {shipping.trackingUrl ? (
                    <a href={shipping.trackingUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-hema hover:underline">
                      {shipping.trackingNumber} <ExternalLink className="size-3.5" aria-hidden />
                    </a>
                  ) : (
                    shipping.trackingNumber
                  )}
                </>
              )}
              {shipping.fee > 0 && <span className="text-ink-2"> · fee ₱{pesos(shipping.fee)}{shipping.feeCharged ? ", charged to the customer" : ""}</span>}
            </p>
          ) : (
            <p className="text-sm text-ink-3">Not set: how it goes, and the courier&apos;s tracking number.</p>
          )}
          {shipping.status && (
            <p className="mt-1 flex flex-wrap items-center gap-2 text-meta text-ink-2">
              <span className={`inline-flex h-5 items-center rounded-full border px-2 text-stamp uppercase ${TONE[shipping.status] ?? ""}`}>{shipping.statusLabel}</span>
              {shipping.attempts > 1 && <span>Try {shipping.attempts}</span>}
              {shipping.status === "failed" && shipping.failedReason && <span>{shipping.failedReason}</span>}
              {delivered && shipping.onTime !== null && <span>{shipping.onTime ? "On time" : "Late"}</span>}
              {shipping.hasPhoto && (
                <a href={`/inventory/orders/${orderId}/delivery-photo`} target="_blank" rel="noreferrer" className="text-hema hover:underline">Courier&apos;s photo</a>
              )}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {mayChange && (
            <Button size="sm" icon={<Pencil className="size-4" aria-hidden />} onClick={() => setOpen("edit")}>
              {set ? "Change" : "Set shipping"}
            </Button>
          )}
          {issued && may.issue && shipping.status === "out" && !signedFor && (
            <>
              <Button size="sm" icon={<Check className="size-4" aria-hidden />} onClick={() => setOpen("delivered")}>
                Delivered
              </Button>
              <Button size="sm" variant="quiet" icon={<X className="size-4" aria-hidden />} onClick={() => setOpen("failed")}>
                Failed
              </Button>
            </>
          )}
          {issued && may.issue && shipping.status === "failed" && (
            <Button size="sm" icon={<RotateCcw className="size-4" aria-hidden />} loading={busy} onClick={again}>
              Send again
            </Button>
          )}
        </div>
      </div>

      <Modal open={open === "edit"} title="Shipping" onCancel={() => !busy && setOpen(null)} onOk={save} okText="Save" confirmLoading={busy} width={520} destroyOnHidden>
        <div className="space-y-4 pt-2">
          <Choice name="method" legend="How it goes" value={form.method} options={METHODS} onChange={(method) => setForm({ ...form, method })} />
          {form.method === "courier" && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Courier" error={fields.courierId}>
                {(p) => (
                  <Select {...p} value={form.courierId} onChange={(e) => setForm({ ...form, courierId: e.target.value })} placeholder="Pick the courier">
                    {active.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="Tracking number" optional error={fields.trackingNumber} hint="From the courier's waybill.">
                {(p) => <Input {...p} value={form.trackingNumber} onChange={(e) => setForm({ ...form, trackingNumber: e.target.value })} maxLength={60} />}
              </Field>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Shipping fee" optional error={fields.fee}>
              {(p) => <Input {...p} inputMode="decimal" prefix="₱" value={form.fee} onChange={(e) => setForm({ ...form, fee: e.target.value })} placeholder="0.00" />}
            </Field>
            <div className="flex items-end pb-2">
              <Checkbox checked={form.feeCharged} onChange={(e) => setForm({ ...form, feeCharged: e.target.checked })}>
                Charged to the customer
              </Checkbox>
            </div>
          </div>
          <p className="text-meta text-ink-3">A fee charged to the customer goes on their invoice.</p>
          <FormError message={error} />
        </div>
      </Modal>

      <Modal open={open === "delivered"} title="Delivered" onCancel={() => !busy && setOpen(null)} onOk={deliver} okText="Mark delivered" confirmLoading={busy} width={480} destroyOnHidden>
        <div className="space-y-4 pt-2">
          <p className="text-meta text-ink-3">When the courier confirms delivery. If the customer is with you, have them sign on screen instead.</p>
          <Field label="Received by" error={fields.receivedBy}>
            {(p) => <Input {...p} value={receivedBy} onChange={(e) => setReceivedBy(e.target.value)} maxLength={120} autoFocus />}
          </Field>
          <Field label="Courier's proof-of-delivery photo" optional error={fields.photo} hint="PNG or JPEG, up to 3 MB.">
            {(p) => <FileInput {...p} accept="image/png,image/jpeg" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />}
          </Field>
          <FormError message={error} />
        </div>
      </Modal>

      <Modal open={open === "failed"} title="Failed delivery" onCancel={() => !busy && setOpen(null)} onOk={failed} okText="Mark failed" okButtonProps={{ danger: true, disabled: reason.trim().length < 3 }} confirmLoading={busy} width={480} destroyOnHidden>
        <div className="space-y-4 pt-2">
          <Field label="Why" error={fields.reason} hint="Nobody there, refused, wrong address…">
            {(p) => <Textarea {...p} rows={3} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} autoFocus />}
          </Field>
          <FormError message={error} />
        </div>
      </Modal>
    </div>
  );
}

/** The company's couriers: LBC, J&T and Lalamove to start with; add its own, switch one off. */
export function CouriersEditor({ couriers, mayManage }: { couriers: Courier[]; mayManage: boolean }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [form, setForm] = useState({ code: "", name: "", trackingUrl: "" });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  function add() {
    start(async () => {
      const r = await saveCourier(null, { code: form.code.trim(), name: form.name.trim(), trackingUrl: form.trackingUrl.trim() || null });
      if (!r.ok) {
        setFields(r.fields ?? {});
        return setError(r.fields ? null : r.error);
      }
      toast.success(`${form.name.trim()} added`);
      setForm({ code: "", name: "", trackingUrl: "" });
      setFields({});
      setError(null);
      router.refresh();
    });
  }

  function flip(c: Courier) {
    start(async () => {
      const r = await saveCourier(c.id, { isActive: !c.isActive });
      if (!r.ok) return void toast.error(r.error);
      toast.success(c.isActive ? `${c.name} switched off` : `${c.name} switched on`);
      router.refresh();
    });
  }

  return (
    <div className="space-y-5">
      {couriers.length === 0 ? (
        <Empty icon="issuance" title="No couriers" source="LBC, J&T and Lalamove are added for every company; add your own below." />
      ) : (
        <ul className="divide-y divide-rule">
          {couriers.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center gap-3 py-3">
              <Truck className="size-4 text-ink-3" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className={`block text-sm font-semibold ${c.isActive ? "text-ink" : "text-ink-3 line-through"}`}>{c.name}</span>
                <span className="block truncate text-meta text-ink-3">{c.code}{c.trackingUrl ? ` · ${c.trackingUrl}` : " · no tracking page"}</span>
              </span>
              {mayManage && (
                <Button size="sm" variant="quiet" disabled={busy} onClick={() => flip(c)}>
                  {c.isActive ? "Switch off" : "Switch on"}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {mayManage && (
        <form noValidate onSubmit={(e) => (e.preventDefault(), add())} className="border-t border-rule pt-4">
          <p className="mb-3 text-sm font-medium text-ink">Add a courier</p>
          <div className="grid gap-4 sm:grid-cols-[8rem_1fr_2fr]">
            <Field label="Code" error={fields.code}>{(p) => <Input {...p} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} maxLength={20} placeholder="GRAB" />}</Field>
            <Field label="Name" error={fields.name}>{(p) => <Input {...p} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={80} placeholder="Grab Express" />}</Field>
            <Field label="Tracking page" optional error={fields.trackingUrl} hint="With {number} where the tracking number goes.">
              {(p) => <Input {...p} value={form.trackingUrl} onChange={(e) => setForm({ ...form, trackingUrl: e.target.value })} maxLength={300} placeholder="https://…?tracking={number}" />}
            </Field>
          </div>
          <FormError message={error} />
          <Button type="submit" size="sm" className="mt-3" loading={busy}>
            Add courier
          </Button>
        </form>
      )}
    </div>
  );
}
