"use client";

import { Printer, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { deleteInvoice, issueInvoice, recordPayment, removePayment, voidInvoice } from "./actions";
import type { Series } from "./types";

/** Issuing a draft: it takes the next number of the series picked, and posts. */
export function IssueInvoice({ id, series }: { id: string; series: Series[] }) {
  const usable = series.filter((s) => s.isActive && s.left > 0);
  const [seriesId, setSeriesId] = useState(usable[0]?.id ?? "");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  if (!usable.length) {
    return <p className="text-sm text-danger">There are no invoice numbers left to issue from. Add the series from the BIR&apos;s Authority to Print under Invoice numbers.</p>;
  }
  const picked = usable.find((s) => s.id === seriesId);
  return (
    <div className="space-y-3">
      {usable.length > 1 && (
        <Field label="Number from">
          {(p) => (
            <Select {...p} value={seriesId} onChange={(e) => setSeriesId(e.target.value)}>
              {usable.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} · next {s.nextNumber}
                </option>
              ))}
            </Select>
          )}
        </Field>
      )}
      <p className="text-meta text-ink-2">
        It becomes invoice <span className="font-mono font-semibold">{picked?.nextNumber}</span> and is posted to the books. After that it can&apos;t be
        changed, only voided.
      </p>
      <FormError message={error} />
      <Button
        variant="primary"
        loading={pending}
        onClick={() =>
          start(async () => {
            const result = await issueInvoice(id, seriesId || null);
            if (!result.ok) return setError(result.error);
            toast.success(`${result.data.number} issued`);
          })
        }
      >
        Issue the invoice
      </Button>
    </div>
  );
}

export function DeleteDraft({ id }: { id: string }) {
  const router = useRouter();
  return (
    <ConfirmButton
      label="Delete draft"
      icon={<Trash2 className="size-4" aria-hidden />}
      title="Delete this draft?"
      body="It has no number yet, so nothing else changes."
      confirmLabel="Delete draft"
      onConfirm={async () => {
        const result = await deleteInvoice(id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        router.push("/invoices");
      }}
    />
  );
}

/** Voiding an issued invoice: it keeps its number, and its entry is reversed. */
export function VoidInvoice({ id, number }: { id: string; number: string }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  if (!open) return <Button onClick={() => setOpen(true)}>Void</Button>;
  return (
    <div className="w-full space-y-3 rounded-[3px] border border-danger/40 bg-danger-tint/40 p-4">
      <p className="text-sm">
        Void <span className="font-mono font-semibold">{number}</span>? The number stays used and the sale is reversed in the books. Keep the voided
        copies, as the BIR expects every number accounted for.
      </p>
      <Field label="Why" error={error ?? undefined}>
        {(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="Wrong customer" />}
      </Field>
      <div className="flex gap-2">
        <Button
          variant="danger"
          loading={pending}
          onClick={() =>
            start(async () => {
              if (reason.trim().length < 3) return setError("Say why it's voided.");
              const result = await voidInvoice(id, reason.trim());
              if (!result.ok) return setError(result.error);
              toast.success(`${number} voided`);
              setOpen(false);
            })
          }
        >
          Void the invoice
        </Button>
        <Button onClick={() => setOpen(false)}>Keep it</Button>
      </div>
    </div>
  );
}

export function PrintButton() {
  return (
    <Button icon={<Printer className="size-4" aria-hidden />} onClick={() => window.print()}>
      Print
    </Button>
  );
}

/** Money received against an issued invoice. */
export function RecordPayment({ id, owed, methods, org, today }: { id: string; owed: number; methods: { key: string; label: string }[]; org: Org; today: string }) {
  const fmt = makeFormat(org);
  const [open, setOpen] = useState(false);
  const [paidOn, setPaidOn] = useState(today);
  const [amount, setAmount] = useState(String(owed / 10 ** (org.minorUnits ?? 2)));
  const [method, setMethod] = useState(methods[0]?.key ?? "cash");
  const [reference, setReference] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  if (!open) return <Button variant="primary" onClick={() => setOpen(true)}>Record a payment</Button>;
  return (
    <form
      noValidate
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        const cents = fmt.toCentavos(amount);
        if (!cents) return setFields({ amountCentavos: "Enter the amount received." });
        start(async () => {
          const result = await recordPayment(id, { paidOn, amountCentavos: cents, method, reference: reference.trim() || null });
          if (!result.ok) {
            setError(result.error);
            setFields(result.fields ?? {});
            return;
          }
          toast.success("Payment recorded");
          setOpen(false);
          setFields({});
          setError(null);
        });
      }}
    >
      <div className="grid gap-4 sm:grid-cols-4">
        <Field label="Received on" error={fields.paidOn}>
          {(p) => <Input {...p} type="date" max={today} value={paidOn} onChange={(e) => setPaidOn(e.target.value)} />}
        </Field>
        <Field label="Amount" error={fields.amountCentavos} hint={`${fmt.peso(owed)} still owed`}>
          {(p) => <Input {...p} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />}
        </Field>
        <Field label="How" error={fields.method}>
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
        <Field label="Reference" optional error={fields.reference} hint="Deposit slip, check or OR number.">
          {(p) => <Input {...p} value={reference} onChange={(e) => setReference(e.target.value)} maxLength={80} />}
        </Field>
      </div>
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          Record the payment
        </Button>
        <Button type="button" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export function RemovePayment({ id, paymentId }: { id: string; paymentId: string }) {
  return (
    <ConfirmButton
      label="Take off"
      triggerVariant="quiet"
      triggerSize="sm"
      title="Take this payment off?"
      body="Its entry is reversed in the books, and the invoice is owed again. The line stays, marked as taken off."
      confirmLabel="Take it off"
      onConfirm={async () => {
        const result = await removePayment(id, paymentId);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
      }}
    />
  );
}
