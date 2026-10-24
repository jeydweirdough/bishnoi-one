"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { ConfirmButton } from "@/src/modules/finance/platform/ui/confirm";
import { Field, FormError, Input, Select } from "@/src/modules/finance/platform/ui/field";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { deleteBill, payBill, recordBill, removeBillPayment, voidBill } from "@/src/modules/finance/bills/actions";

/** Recording a draft in the books: the purchase, its input VAT, what's owed and the tax withheld. */
export function RecordBill({ id }: { id: string }) {
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  return (
    <div className="space-y-2">
      <p className="text-meta text-ink-2">Recorded, it&apos;s posted to the books and can&apos;t be changed, only voided.</p>
      <FormError message={error} />
      <Button
        variant="primary"
        loading={pending}
        onClick={() =>
          start(async () => {
            const result = await recordBill(id);
            if (!result.ok) return setError(result.error);
            toast.success("Bill recorded");
          })
        }
      >
        Record bill
      </Button>
    </div>
  );
}

export function DeleteBillDraft({ id }: { id: string }) {
  const router = useRouter();
  return (
    <ConfirmButton
      label="Delete draft"
      icon={<Trash2 className="size-4" aria-hidden />}
      title="Delete this draft?"
      body="It isn't in the books yet, so nothing else changes."
      confirmLabel="Delete draft"
      onConfirm={async () => {
        const result = await deleteBill(id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        router.push("/finance/bills");
      }}
    />
  );
}

export function VoidBill({ id, label }: { id: string; label: string }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  if (!open) return <Button onClick={() => setOpen(true)}>Void</Button>;
  return (
    <div className="w-full space-y-3 rounded-[3px] border border-danger/40 bg-danger-tint/40 p-4">
      <p className="text-sm">Void {label}? Its entry is reversed in the books, and it leaves the BIR lists.</p>
      <Field label="Reason for voiding" error={error ?? undefined}>
        {(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="Entered twice" />}
      </Field>
      <div className="flex gap-2">
        <Button
          variant="danger"
          loading={pending}
          onClick={() =>
            start(async () => {
              if (reason.trim().length < 3) return setError("Enter the reason for voiding.");
              const result = await voidBill(id, reason.trim());
              if (!result.ok) return setError(result.error);
              toast.success("Bill voided");
              setOpen(false);
            })
          }
        >
          Void bill
        </Button>
        <Button onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </div>
  );
}

/** Money paid to the supplier against a recorded bill. */
export function PayBill({ id, owed, methods, org, today }: { id: string; owed: number; methods: { key: string; label: string }[]; org: Org; today: string }) {
  const fmt = makeFormat(org);
  const [open, setOpen] = useState(false);
  const [paidOn, setPaidOn] = useState(today);
  const [amount, setAmount] = useState(String(owed / 10 ** (org.minorUnits ?? 2)));
  const [method, setMethod] = useState(methods.find((m) => m.key === "bank")?.key ?? methods[0]?.key ?? "cash");
  const [reference, setReference] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  if (!open) return <Button variant="primary" onClick={() => setOpen(true)}>Record payment</Button>;
  return (
    <form
      noValidate
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        const cents = fmt.toCentavos(amount);
        if (!cents) return setFields({ amountCentavos: "Enter the amount paid." });
        start(async () => {
          const result = await payBill(id, { paidOn, amountCentavos: cents, method, reference: reference.trim() || null });
          if (!result.ok) {
            setError(result.error);
            setFields(result.fields ?? {});
            return;
          }
          toast.success("Payment recorded");
          setOpen(false);
        });
      }}
    >
      <div className="grid gap-4 sm:grid-cols-4">
        <Field label="Payment date" error={fields.paidOn}>
          {(p) => <Input {...p} type="date" max={today} value={paidOn} onChange={(e) => setPaidOn(e.target.value)} />}
        </Field>
        <Field label="Amount" error={fields.amountCentavos} hint={`Owed: ${fmt.peso(owed)}.`}>
          {(p) => <Input {...p} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />}
        </Field>
        <Field label="Paid by" error={fields.method}>
          {(p) => (
            <Select {...p} value={method} onChange={(e) => setMethod(e.target.value)}>
              {methods.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Reference" optional error={fields.reference} hint="Check or transfer number.">
          {(p) => <Input {...p} value={reference} onChange={(e) => setReference(e.target.value)} maxLength={80} />}
        </Field>
      </div>
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          Record payment
        </Button>
        <Button type="button" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export function RemoveBillPayment({ id, paymentId }: { id: string; paymentId: string }) {
  return (
    <ConfirmButton
      label="Reverse"
      triggerVariant="quiet"
      triggerSize="sm"
      title="Reverse this payment?"
      body="Its entry is reversed in the books, and the bill is owed again. The line stays, marked as reversed."
      confirmLabel="Reverse payment"
      onConfirm={async () => {
        const result = await removeBillPayment(id, paymentId);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success("Payment reversed");
      }}
    />
  );
}
