"use client";

import { CheckCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Select, Textarea } from "@/src/platform/ui/field";
import { Flag } from "@/src/platform/ui/marks";
import { checkPrescription, type CheckInput } from "../actions/pharmacy";
import type { Flag as RxFlag, Prescription } from "../lib/types";

type Verdict = CheckInput["status"];
type Option = { id: string; label: string; status: string; rxClass: string };

const VERDICTS: { value: Verdict; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "verified", label: "Verified" },
  { value: "needs_clarification", label: "Needs clarification" },
  { value: "rejected", label: "Rejected" },
];

const SUBMIT: Record<Verdict, string> = {
  pending: "Save and keep checking",
  verified: "Verify prescription",
  needs_clarification: "Hold for clarification",
  rejected: "Reject prescription",
};

/**
 * The pharmacist's check: match each medicine as written to the catalogue,
 * tick every check, then give a verdict. "Verify" is only offered once every
 * box is ticked and every medicine matched; the API holds the same line, and
 * also refuses anything a red flag blocks (a date out of range, a dangerous
 * drug with no prescriber licence).
 */
export function CheckForm({ rx, medicines, canCheck }: { rx: Prescription; medicines: Option[]; canCheck: boolean }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [ticks, setTicks] = useState<Record<string, boolean>>(Object.fromEntries(rx.checks.map((c) => [c.key, c.done])));
  const [matches, setMatches] = useState<Record<string, string>>(Object.fromEntries(rx.items.map((i) => [i.id, i.medicine?.id ?? ""])));
  const [verdict, setVerdict] = useState<Verdict>(rx.status === "received" ? "pending" : (rx.status as Verdict));
  const [notes, setNotes] = useState(rx.verificationNotes ?? "");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  const locked = !canCheck || rx.status === "rejected" || (rx.status === "verified" && rx.dispensed !== "none");
  const byCheck = useMemo(() => {
    const out: Record<string, RxFlag[]> = {};
    for (const f of rx.flags) (out[f.check] ??= []).push(f);
    return out;
  }, [rx.flags]);
  const blocked = rx.flags.some((f) => f.level === "block" && f.check !== "medicine");
  const open = rx.checks.filter((c) => !ticks[c.key]);
  const unmatched = rx.items.filter((i) => !matches[i.id]);
  const canVerify = open.length === 0 && unmatched.length === 0;
  const matchChanged = rx.items.some((i) => (i.medicine?.id ?? "") !== matches[i.id]);
  // Already verified: it can be sent back (pending, clarification, rejected), not verified again.
  const standing = rx.status === "verified" && verdict === "verified";

  function submit() {
    start(async () => {
      const result = await checkPrescription(rx.id, {
        checks: ticks,
        matches: rx.items.map((i) => ({ itemId: i.id, medicineId: matches[i.id] || null })),
        status: verdict,
        notes: notes.trim() || null,
      });
      if (result.ok) {
        setError(null);
        setFields({});
        toast.success(verdict === "verified" ? "Verified: it's in the dispensing queue" : verdict === "pending" ? "Check saved" : "Saved", {
          description: rx.number,
        });
        router.refresh();
        return;
      }
      setError(result.error);
      setFields(result.fields ?? {});
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-6"
    >
      {/* Matching belongs to "Medicine name": what was written, and the catalogue medicine it is. */}
      {!locked && !standing && (
        <fieldset className="space-y-3">
          <legend className="mb-1 text-sm font-semibold text-ink">Match each medicine to the catalogue</legend>
          {rx.items.map((item, n) => (
            <Field
              key={item.id}
              label={`“${item.writtenAs}” × ${item.quantity}`}
              error={fields[`matches.${n}.medicineId`]}
              hint={item.directions ?? undefined}
            >
              {(p) => (
                <Select {...p} value={matches[item.id]} onChange={(e) => setMatches({ ...matches, [item.id]: e.target.value })}>
                  <option value="">Not matched yet</option>
                  {medicines.map((m) => (
                    <option key={m.id} value={m.id} disabled={m.status === "inactive"}>
                      {m.label}
                      {m.rxClass === "dangerous" ? " · dangerous drug" : m.rxClass === "otc" ? " · OTC" : ""}
                      {m.status !== "active" ? ` (${m.status})` : ""}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          ))}
          {matchChanged && <p className="text-meta text-ink-3">Save the check to see stock and flags for the medicines you matched.</p>}
        </fieldset>
      )}

      <fieldset>
        <legend className="mb-2 flex w-full items-center justify-between gap-3 text-sm font-semibold text-ink">
          <span>Checks</span>
          {!locked && !standing && (
            <button
              type="button"
              className="text-meta font-semibold text-hema hover:underline"
              onClick={() => setTicks(Object.fromEntries(rx.checks.map((c) => [c.key, open.length > 0])))}
            >
              {open.length > 0 ? "Tick all" : "Clear all"}
            </button>
          )}
        </legend>
        <ul className="divide-y divide-rule rounded-[3px] border border-rule">
          {rx.checks.map((c) => (
            <li key={c.key} className="px-3 py-2.5">
              <label className={`flex items-start gap-3 text-sm ${locked || standing ? "" : "cursor-pointer"}`}>
                <input
                  type="checkbox"
                  className="mt-0.5 size-4 accent-[var(--color-hema)]"
                  checked={Boolean(ticks[c.key])}
                  disabled={locked || standing}
                  onChange={(e) => setTicks({ ...ticks, [c.key]: e.target.checked })}
                />
                <span className="min-w-0 flex-1">
                  <span className={ticks[c.key] ? "text-ink" : "text-ink-2"}>{c.label}</span>
                  {(byCheck[c.key] ?? []).map((f) => (
                    <span key={f.message} className="mt-1 block">
                      {f.level === "block" ? (
                        <Flag letter="!">{f.message}</Flag>
                      ) : (
                        <span className="text-meta text-ink-2">{f.message}</span>
                      )}
                    </span>
                  ))}
                </span>
              </label>
            </li>
          ))}
        </ul>
        {fields.checks && <p className="mt-1 text-meta text-danger">{fields.checks}</p>}
      </fieldset>

      {!locked && (
        <fieldset className="space-y-4">
          <legend className="mb-1 text-sm font-semibold text-ink">Verification</legend>
          <Choice
            name="verdict"
            legend="Status"
            value={verdict}
            onChange={setVerdict}
            options={VERDICTS.map((v) => ({ ...v, label: v.label }))}
          />
          {standing && (
            <p className="text-meta text-ink-2">
              Verified. To change anything before it&apos;s dispensed, send it back: pick Pending, Needs clarification or Rejected.
            </p>
          )}
          {verdict === "verified" && !standing && !canVerify && (
            <p className="text-meta text-ink-2">
              {unmatched.length > 0 ? `Match ${unmatched.length === 1 ? "the medicine" : `all ${rx.items.length} medicines`} and ` : ""}
              {open.length > 0 ? `tick the ${open.length} open check${open.length === 1 ? "" : "s"}` : "save"} to verify.
            </p>
          )}
          {verdict === "verified" && !standing && canVerify && blocked && (
            <p className="text-meta text-ink-2">A red flag above stops verification. Hold it for clarification instead.</p>
          )}
          <Field
            label="Notes"
            optional={verdict === "pending" || verdict === "verified"}
            error={fields.notes}
            hint={verdict === "needs_clarification" ? "What to ask, and whom: the next person picks it up from here." : verdict === "rejected" ? "Why it won't be dispensed." : undefined}
          >
            {(p) => <Textarea {...p} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={4000} />}
          </Field>
          <FormError message={error} />
          <Button
            type="submit"
            variant={verdict === "rejected" ? "danger" : "primary"}
            loading={pending}
            disabled={standing || (verdict === "verified" && (!canVerify || blocked))}
            icon={verdict === "verified" ? <CheckCheck className="size-4" aria-hidden /> : undefined}
          >
            {standing ? "Verified" : rx.status === "verified" && verdict !== "rejected" ? "Send back for checking" : SUBMIT[verdict]}
          </Button>
        </fieldset>
      )}
    </form>
  );
}
