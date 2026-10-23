"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { deleteBill, recordBill, voidBill } from "./actions";
import type { Bill } from "./types";

/** Recording a draft: it posts to the books and can't be changed after, only voided. */
export function RecordBill({ bill }: { bill: Bill }) {
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  return (
    <div className="space-y-3">
      <p className="text-meta text-ink-2">
        Recording posts it to the books: the expense and its VAT, against what&apos;s owed {bill.supplier.name} and the tax withheld for the BIR. After that it
        can&apos;t be changed, only voided.
        {bill.documentMissing && <span className="text-due-today"> The supplier&apos;s invoice isn&apos;t attached yet: it can be added after recording too.</span>}
        {!bill.checkedPo || !bill.checkedDr ? <span className="text-due-today"> Not marked as checked against the {[!bill.checkedPo && "PO", !bill.checkedDr && "delivery receipt"].filter(Boolean).join(" and ")}.</span> : null}
      </p>
      <FormError message={error} />
      <Button
        variant="primary"
        loading={pending}
        onClick={() =>
          start(async () => {
            const result = await recordBill(bill.id);
            if (!result.ok) return setError(result.error);
            toast.success(`Bill ${result.data.no} recorded`, { description: "Posted to the books." });
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
      body="Nothing has been posted yet, so nothing else changes. Its attached files go with it."
      confirmLabel="Delete draft"
      onConfirm={async () => {
        const result = await deleteBill(id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        router.push("/bills");
      }}
    />
  );
}

/** Voiding a recorded bill: its entry is reversed today; the bill stays, marked void. */
export function VoidBill({ id, label }: { id: string; label: string }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  if (!open) return <Button onClick={() => setOpen(true)}>Void</Button>;
  return (
    <div className="w-full space-y-3 rounded-[3px] border border-danger/40 bg-danger-tint/40 p-4">
      <p className="text-sm">Void {label}? Its entry is reversed in the books today. The bill stays, marked void; enter it again if it needs correcting.</p>
      <Field label="Reason for voiding" error={error ?? undefined}>
        {(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="Wrong amount" />}
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
              toast.success(`${label} voided`);
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
