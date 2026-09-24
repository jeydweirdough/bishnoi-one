"use client";

import { MapPin, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useId, useMemo, useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { logVisit } from "../../actions/field";
import { localDateTime } from "../crm/words";
import type { VisitOutcome } from "./types";
import { OUTCOMES } from "./words";

type Doctor = { id: string; name: string };

/**
 * A visit to a doctor and what came of it. A collection asks for the amount
 * and the receipt; anything else, just a note. On a doctor's page the doctor
 * is fixed; elsewhere it's picked from the agent's own.
 */
function LogVisitForm({ org, now, doctor, doctors = [], onDone }: { org: Org; now: string; doctor?: Doctor; doctors?: Doctor[]; onDone: () => void }) {
  const fmt = useMemo(() => makeFormat(org), [org]);
  const [companyId, setCompanyId] = useState(doctor?.id ?? "");
  const [outcome, setOutcome] = useState<VisitOutcome>("collected");
  const [at, setAt] = useState(() => localDateTime(new Date(now), org.timezone));
  const [amount, setAmount] = useState("");
  const [receipt, setReceipt] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [pending, start] = useTransition();
  const collecting = outcome === "collected";

  function submit() {
    const cents = collecting ? fmt.toCentavos(amount) : null;
    if (collecting && !cents) {
      setFields({ amountCentavos: "Enter how much was collected." });
      return;
    }
    start(async () => {
      const result = await logVisit({
        companyId,
        outcome,
        visitedAt: at || null,
        amountCentavos: cents,
        receiptNo: collecting ? receipt.trim() || null : null,
        notes: notes.trim() || null,
      });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      const v = result.data;
      toast.success(v.outcome === "collected" ? `Collected ${fmt.peso(v.amountCentavos)}` : "Visit logged", { description: v.company.name });
      setAmount("");
      setReceipt("");
      setNotes("");
      setError(null);
      setFields({});
      onDone();
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-4"
    >
      {!doctor && (
        <Field label="Doctor" error={fields.companyId}>
          {(p) => (
            <Select {...p} value={companyId} onChange={(e) => setCompanyId(e.target.value)} required>
              <option value="">Pick a doctor</option>
              {doctors.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
      )}
      <Choice<VisitOutcome> name="outcome" legend="What came of it" value={outcome} onChange={setOutcome} options={OUTCOMES.map((o) => ({ value: o.value, label: o.label }))} />
      {collecting && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Amount collected" error={fields.amountCentavos}>
            {(p) => <Input {...p} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" autoFocus={!!doctor} />}
          </Field>
          <Field label="Receipt number" optional hint="The OR or acknowledgment receipt you gave." error={fields.receiptNo}>
            {(p) => <Input {...p} value={receipt} onChange={(e) => setReceipt(e.target.value)} maxLength={40} />}
          </Field>
        </div>
      )}
      <Field label="When" error={fields.visitedAt}>
        {(p) => <Input {...p} type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} />}
      </Field>
      <Field label="Notes" optional error={fields.notes}>
        {(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder={collecting ? "Anything about the payment" : "What happened, and what's next"} />}
      </Field>
      <FormError message={error} />
      <Button type="submit" variant="primary" loading={pending} disabled={!companyId}>
        {collecting ? "Log collection" : "Log visit"}
      </Button>
    </form>
  );
}

/** "Log visit": a button that opens the form in a panel. */
export function LogVisitButton({
  variant = "default",
  label = "Log visit",
  ...form
}: {
  variant?: "primary" | "default";
  label?: string;
  org: Org;
  now: string;
  doctor?: Doctor;
  doctors?: Doctor[];
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const router = useRouter();
  const titleId = useId();
  return (
    <>
      <Button variant={variant} icon={<MapPin className="size-4" aria-hidden />} onClick={() => dialog.current?.showModal()}>
        {label}
      </Button>
      <dialog ref={dialog} aria-labelledby={titleId} className="m-auto w-[min(34rem,calc(100vw-2rem))] rounded-[3px] bg-sheet p-0 text-ink shadow-overlay backdrop:bg-ink/30">
        <div className="flex items-center justify-between border-b border-rule px-5 py-3">
          <h2 id={titleId} className="text-heading">
            {form.doctor ? `Visit to ${form.doctor.name}` : "Log visit"}
          </h2>
          <button type="button" onClick={() => dialog.current?.close()} className="rounded-[3px] p-1 text-ink-3 hover:bg-bench hover:text-ink" aria-label="Close">
            <X className="size-4" aria-hidden />
          </button>
        </div>
        <div className="max-h-[75vh] overflow-y-auto px-5 pt-4 pb-5">
          <LogVisitForm
            {...form}
            onDone={() => {
              dialog.current?.close();
              router.refresh();
            }}
          />
        </div>
      </dialog>
    </>
  );
}
