"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { voucherStep } from "./actions";
import type { Voucher } from "./types";

type Asking = null | "return" | "cancel" | "void" | "release";

const ASK: Record<"return" | "cancel" | "void", { title: (v: Voucher) => string; field: string; placeholder: string; go: string; done: string }> = {
  return: {
    title: (v) => `Return ${v.number} to ${v.preparedBy}? They're told why, correct it and submit it again.`,
    field: "What needs correcting",
    placeholder: "Wrong bank account",
    go: "Return for correction",
    done: "returned for correction",
  },
  cancel: { title: (v) => `Cancel ${v.number}? Nothing has been paid or posted; the bills it held are free again.`, field: "Why it's cancelled", placeholder: "Paid another way", go: "Cancel voucher", done: "cancelled" },
  void: {
    title: (v) => `Void ${v.number}? Its entry is reversed in the books today, and the bills it paid are owed again.`,
    field: "Why it's voided",
    placeholder: "Check bounced",
    go: "Void voucher",
    done: "voided",
  },
};

/** The steps this person may take on this voucher now (the API holds the same rules). */
export function VoucherSteps({ voucher: v, today }: { voucher: Voucher; today: string }) {
  const [asking, setAsking] = useState<Asking>(null);
  const [reason, setReason] = useState("");
  const [release, setRelease] = useState({ paidOn: today, bankReference: "", checkNumber: "", checkDate: today, note: "" });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function run(step: Parameters<typeof voucherStep>[1], body: object, said: string) {
    start(async () => {
      const result = await voucherStep(v.id, step, body);
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(`${v.number} ${said}`);
      setAsking(null);
      setReason("");
      setError(null);
      setFields({});
    });
  }

  const nothing = !(v.canSubmit || v.canRelease || v.canReturn || v.canCancel || v.canVoid);
  if (nothing) return null;

  if (asking === "release") {
    return (
      <form
        noValidate
        className="w-full space-y-3 rounded-[3px] border border-rule bg-sheet p-4"
        onSubmit={(e) => {
          e.preventDefault();
          run(
            "release",
            {
              paidOn: release.paidOn,
              bankReference: release.bankReference.trim() || null,
              checkNumber: release.checkNumber.trim() || null,
              checkDate: v.method === "check" ? release.checkDate || null : null,
              note: release.note.trim() || null,
            },
            "released: paid and posted",
          );
        }}
      >
        <p className="text-sm">
          Release {v.number}: the money leaves <span className="font-semibold">{v.paidFrom ? `${v.paidFrom.code} · ${v.paidFrom.name}` : "the account picked"}</span> and it&apos;s posted to the
          books. Mira&apos;s approval stays in the bank&apos;s own system.
        </p>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Paid on" error={fields.paidOn}>
            {(p) => <Input {...p} type="date" max={today} value={release.paidOn} onChange={(e) => setRelease({ ...release, paidOn: e.target.value })} />}
          </Field>
          {v.method === "check" ? (
            <>
              <Field label="Check number" error={fields.checkNumber}>
                {(p) => <Input {...p} value={release.checkNumber} onChange={(e) => setRelease({ ...release, checkNumber: e.target.value })} maxLength={40} />}
              </Field>
              <Field label="Check date" error={fields.checkDate}>
                {(p) => <Input {...p} type="date" value={release.checkDate} onChange={(e) => setRelease({ ...release, checkDate: e.target.value })} />}
              </Field>
            </>
          ) : (
            <Field label="Bank reference" optional error={fields.bankReference} hint="The transfer's reference number.">
              {(p) => <Input {...p} value={release.bankReference} onChange={(e) => setRelease({ ...release, bankReference: e.target.value })} maxLength={80} />}
            </Field>
          )}
        </div>
        <Field label="Note" optional error={fields.note} hint="e.g. approved in the bank by Ma'am Mira.">
          {(p) => <Input {...p} value={release.note} onChange={(e) => setRelease({ ...release, note: e.target.value })} maxLength={300} />}
        </Field>
        <FormError message={error} />
        <div className="flex gap-2">
          <Button type="submit" variant="primary" loading={pending}>
            Release and post
          </Button>
          <Button onClick={() => setAsking(null)}>Not yet</Button>
        </div>
      </form>
    );
  }

  if (asking) {
    const a = ASK[asking];
    return (
      <div className="w-full space-y-3 rounded-[3px] border border-danger/40 bg-danger-tint/40 p-4">
        <p className="text-sm">{a.title(v)}</p>
        <Field label={a.field} error={fields.reason ?? (error ?? undefined)}>
          {(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder={a.placeholder} autoFocus />}
        </Field>
        <div className="flex gap-2">
          <Button
            variant="danger"
            loading={pending}
            onClick={() => {
              if (reason.trim().length < 3) return setFields({ reason: "Say why, in a few words." });
              run(asking, { reason: reason.trim() }, a.done);
            }}
          >
            {a.go}
          </Button>
          <Button onClick={() => setAsking(null)}>Keep it</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {v.canSubmit && (
          <Button variant="primary" loading={pending} onClick={() => run("submit", {}, v.status === "returned" ? "resubmitted: ready to release" : "submitted: ready to release")}>
            {v.status === "returned" ? "Submit again" : "Submit for release"}
          </Button>
        )}
        {v.canRelease && (
          <Button variant="primary" onClick={() => setAsking("release")}>
            Release…
          </Button>
        )}
        {v.canReturn && <Button onClick={() => setAsking("return")}>Return for correction…</Button>}
        {v.canCancel && <Button onClick={() => setAsking("cancel")}>Cancel voucher…</Button>}
        {v.canVoid && <Button onClick={() => setAsking("void")}>Void…</Button>}
      </div>
      <FormError message={error} />
    </div>
  );
}
