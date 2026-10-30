"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { ConfirmButton } from "@/src/modules/finance/platform/ui/confirm";
import { Field, FormError, Input } from "@/src/modules/finance/platform/ui/field";
import { deletePettyCash, pettyCashStep } from "@/src/modules/finance/petty-cash/actions";
import type { PettyCashVoucher } from "@/src/modules/finance/petty-cash/types";

/** A reason box (return, void): at least three characters, as the API asks. */
function ReasonBox({ intro, label, placeholder, confirm, pending, error, onConfirm, onCancel }: {
  intro: string; label: string; placeholder: string; confirm: string; pending: boolean; error: string | null; onConfirm: (reason: string) => void; onCancel: () => void;
}) {
  const [reason, setReason] = useState("");
  const [short, setShort] = useState<string | null>(null);
  return (
    <div className="w-full space-y-3 rounded-[3px] border border-danger/40 bg-danger-tint/40 p-4">
      <p className="text-sm">{intro}</p>
      <Field label={label} error={short ?? error ?? undefined}>
        {(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder={placeholder} autoFocus />}
      </Field>
      <div className="flex gap-2">
        <Button
          variant="danger"
          loading={pending}
          onClick={() => {
            if (reason.trim().length < 3) return setShort("Say why, in a few words.");
            setShort(null);
            onConfirm(reason.trim());
          }}
        >
          {confirm}
        </Button>
        <Button onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

/**
 * The step this person may take now: submit it for checking (whoever makes petty cash vouchers,
 * once every receipt is attached); or check it against its receipts and post it, or return it with
 * the reason (someone who may check, never whoever made or submitted it: the API's canCheck).
 */
export function PettyCashSteps({ voucher: v }: { voucher: PettyCashVoucher }) {
  const [returning, setReturning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function run(step: "submit" | "check" | "return", body: object, said: string) {
    start(async () => {
      const result = await pettyCashStep(v.id, step, body);
      if (!result.ok) return setError(result.error);
      toast.success(`Petty cash voucher ${result.data.number} ${said}`);
      setReturning(false);
      setError(null);
    });
  }

  const editable = v.status === "draft" || v.status === "returned";
  if (returning) {
    return (
      <ReasonBox
        intro={`Return ${v.number} to whoever submitted it? They're told why, correct it and submit it again.`}
        label="What needs correcting"
        placeholder="Receipt 2 is not an official receipt"
        confirm="Return for correction"
        pending={pending}
        error={error}
        onConfirm={(reason) => run("return", { reason }, "returned for correction")}
        onCancel={() => setReturning(false)}
      />
    );
  }

  return (
    <div className="space-y-3">
      {editable && v.canEdit && v.missingReceipts > 0 && (
        <p className="text-sm text-due-today">
          {v.missingReceipts === 1 ? "1 receipt is" : `${v.missingReceipts} receipts are`} still missing: attach a photo or PDF on{" "}
          {v.missingReceipts === 1 ? "its line" : "each line"} below, then submit.
        </p>
      )}
      {v.canSubmit && <p className="text-meta text-ink-2">Submitting sends it to be checked against its receipts. It can&apos;t be changed while it waits; it&apos;s posted to the books only once it&apos;s checked.</p>}
      {v.canCheck && (
        <p className="text-meta text-ink-2">
          Open each receipt beside its line and compare the store, receipt number, date and amount. Checked, it&apos;s posted to the books on the voucher&apos;s date: each
          line&apos;s account and its input VAT, paid out of {v.fund.name}.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {v.canSubmit && (
          <Button variant="primary" loading={pending} onClick={() => run("submit", {}, v.status === "returned" ? "submitted again: waiting to be checked" : "submitted: waiting to be checked")}>
            {v.status === "returned" ? "Submit again" : "Submit for checking"}
          </Button>
        )}
        {v.canCheck && (
          <Button variant="primary" loading={pending} onClick={() => run("check", {}, "checked and posted")}>
            Check and post
          </Button>
        )}
        {v.canReturn && <Button onClick={() => setReturning(true)}>Return for correction…</Button>}
      </div>
      <FormError message={error} />
    </div>
  );
}

/** Voiding a posted voucher: its entry is reversed today; the voucher, its receipts and history stay. */
export function VoidPettyCash({ id, number }: { id: string; number: string }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  if (!open) return <Button onClick={() => setOpen(true)}>Void</Button>;
  return (
    <ReasonBox
      intro={`Void ${number}? Its entry is reversed in the books today. The voucher stays, marked void; enter it again if it needs correcting.`}
      label="Reason for voiding"
      placeholder="Entered twice"
      confirm="Void voucher"
      pending={pending}
      error={error}
      onConfirm={(reason) =>
        start(async () => {
          const result = await pettyCashStep(id, "void", { reason });
          if (!result.ok) return setError(result.error);
          toast.success(`${number} voided`);
          setOpen(false);
        })
      }
      onCancel={() => setOpen(false)}
    />
  );
}

export function DeletePettyCash({ id }: { id: string }) {
  const router = useRouter();
  return (
    <ConfirmButton
      label="Delete"
      icon={<Trash2 className="size-4" aria-hidden />}
      title="Delete this voucher?"
      body="Nothing has been posted yet, so nothing else changes. Its attached receipts go with it."
      confirmLabel="Delete voucher"
      onConfirm={async () => {
        const result = await deletePettyCash(id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        router.push("/finance/petty-cash");
      }}
    />
  );
}
