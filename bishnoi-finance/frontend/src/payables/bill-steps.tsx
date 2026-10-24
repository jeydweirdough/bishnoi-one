"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { billStep, deleteBill, voidBill } from "./actions";
import type { Bill } from "./types";

/** The step this person may take on this bill now (Aubrey's flow, 2026-10-23): submit it for
 *  approval; approve it (Malou; Cristal backup); check the tax withheld (Mel); or return it with
 *  the reason. It's posted to the books when it clears; after that it's only voided. */
export function BillSteps({ bill }: { bill: Bill }) {
  const [returning, setReturning] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function run(step: "submit" | "approve" | "check" | "return", body: object, said: (b: Bill) => string) {
    start(async () => {
      const result = await billStep(bill.id, step, body);
      if (!result.ok) return setError(result.error);
      toast.success(`Bill ${result.data.no} ${said(result.data)}`);
      setReturning(false);
      setReason("");
      setError(null);
    });
  }

  if (!(bill.canSubmit || bill.canApprove || bill.canCheck || bill.canReturn)) return null;
  const cleared = (b: Bill) => (b.state === "ready" ? "approved and posted: ready to pay" : "approved: waiting for the tax withheld to be checked");

  if (returning) {
    return (
      <div className="w-full space-y-3 rounded-[3px] border border-danger/40 bg-danger-tint/40 p-4">
        <p className="text-sm">Return bill {bill.no} to whoever submitted it? They&apos;re told why, correct it and submit it again; it goes to approval from the start.</p>
        <Field label="What needs correcting" error={error ?? undefined}>
          {(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="Wrong withholding code" autoFocus />}
        </Field>
        <div className="flex gap-2">
          <Button
            variant="danger"
            loading={pending}
            onClick={() => {
              if (reason.trim().length < 3) return setError("Say why, in a few words.");
              run("return", { reason: reason.trim() }, () => "returned for correction");
            }}
          >
            Return for correction
          </Button>
          <Button onClick={() => setReturning(false)}>Keep it</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {bill.canSubmit && (
        <p className="text-meta text-ink-2">
          Submitting sends it for approval{bill.needsCheck ? ", then for the tax withheld to be checked" : ""}. It&apos;s posted to the books only once it clears, and can&apos;t be
          changed while it waits.
          {bill.documentMissing && <span className="text-due-today"> The supplier&apos;s invoice isn&apos;t attached yet.</span>}
          {!bill.checkedPo || !bill.checkedDr ? <span className="text-due-today"> Not marked as checked against the {[!bill.checkedPo && "PO", !bill.checkedDr && "delivery receipt"].filter(Boolean).join(" and ")}.</span> : null}
        </p>
      )}
      {bill.canApprove && (
        <p className="text-meta text-ink-2">
          Approving {bill.needsCheck ? "sends it to have its tax withheld checked; then it's posted" : "posts it to the books"}: the expense and its VAT, against what&apos;s owed{" "}
          {bill.supplier.name}
          {bill.needsCheck ? " and the tax withheld for the BIR" : ""}. Then it&apos;s ready to pay.
          {bill.documentMissing && <span className="text-due-today"> The supplier&apos;s invoice isn&apos;t attached.</span>}
        </p>
      )}
      {bill.canCheck && <p className="text-meta text-ink-2">Check each line&apos;s withholding code and rate below. Checked, it&apos;s posted to the books and ready to pay.</p>}
      <div className="flex flex-wrap gap-2">
        {bill.canSubmit && (
          <Button variant="primary" loading={pending} onClick={() => run("submit", {}, () => (bill.state === "returned" ? "submitted again: waiting for approval" : "submitted: waiting for approval"))}>
            {bill.state === "returned" ? "Submit again" : "Submit for approval"}
          </Button>
        )}
        {bill.canApprove && (
          <Button variant="primary" loading={pending} onClick={() => run("approve", {}, cleared)}>
            Approve
          </Button>
        )}
        {bill.canCheck && (
          <Button variant="primary" loading={pending} onClick={() => run("check", {}, () => "checked and posted: ready to pay")}>
            Tax withheld checked
          </Button>
        )}
        {bill.canReturn && <Button onClick={() => setReturning(true)}>Return for correction…</Button>}
      </div>
      <FormError message={error} />
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
