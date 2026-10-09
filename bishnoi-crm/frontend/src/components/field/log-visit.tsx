"use client";

import { Modal } from "antd";
import { MapPin } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { logVisit } from "../../actions/field";
import { localDateTime } from "../crm/words";
import type { VisitOutcome } from "./types";
import { DetailingFields, type DetailDraft } from "./detailing-fields";
import { locate, NO_LOCATION } from "./where";
import { OUTCOMES } from "./words";
import { useTerms } from "@/src/components/terms/provider";
import { lower } from "@/src/components/terms/terms";

type Doctor = { id: string; name: string };

/**
 * A visit to a doctor and what came of it. A collection asks for the amount
 * and the receipt; anything else, just a note. On a doctor's page the doctor
 * is fixed; elsewhere it's picked from the agent's own.
 */
function LogVisitForm({
  org,
  now,
  doctor,
  doctors = [],
  requireLocation = false,
  onDone,
}: {
  org: Org;
  now: string;
  doctor?: Doctor;
  doctors?: Doctor[];
  /** A field agent's visit can't be logged without where they are. */
  requireLocation?: boolean;
  onDone: () => void;
}) {
  const fmt = useMemo(() => makeFormat(org), [org]);
  const [companyId, setCompanyId] = useState(doctor?.id ?? "");
  const terms = useTerms();
  const [outcome, setOutcome] = useState<VisitOutcome>("collected");
  const [at, setAt] = useState(() => localDateTime(new Date(now), org.timezone));
  const [amount, setAmount] = useState("");
  const [receipt, setReceipt] = useState("");
  const [notes, setNotes] = useState("");
  const [details, setDetails] = useState<DetailDraft[]>([]);
  const [objective, setObjective] = useState("");
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
    const used = details.filter((d) => d.productId || d.reaction || d.message.trim());
    const missing: Record<string, string> = {};
    used.forEach((d, i) => {
      if (!d.productId) missing[`detailing.${i}.productId`] = "Pick the product.";
      if (!d.reaction) missing[`detailing.${i}.reaction`] = `Pick how the ${lower(terms.visited.one)} took it.`;
    });
    if (Object.keys(missing).length) {
      setDetails(used);
      setFields(missing);
      return;
    }
    start(async () => {
      // Where the phone is now, if it says: the visit is placed at (or away
      // from) the clinic by it. The browser asks the person the first time.
      const found = await locate();
      if (!found.ok && requireLocation) {
        setError(`${NO_LOCATION[found.why]} Your location is needed to log a visit: turn it on, then log it again.`);
        return;
      }
      const location = found.ok ? found.where : null;
      const result = await logVisit({
        companyId,
        outcome,
        visitedAt: at || null,
        amountCentavos: cents,
        receiptNo: collecting ? receipt.trim() || null : null,
        notes: notes.trim() || null,
        detailing: used.map((d) => ({ productId: d.productId, message: d.message.trim() || null, reaction: d.reaction as Exclude<typeof d.reaction, "">})),
        nextObjective: objective.trim() || null,
        location,
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
      setDetails([]);
      setObjective("");
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
        <Field label={terms.visited.one} error={fields.companyId}>
          {(p) => (
            <Select {...p} value={companyId} onChange={(e) => setCompanyId(e.target.value)} required>
              <option value="">Pick a {lower(terms.visited.one)}</option>
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
      {outcome !== "not_in" && (
        <DetailingFields companyId={companyId} rows={details} onRows={setDetails} objective={objective} onObjective={setObjective} errors={fields} />
      )}
      <Field label="Notes" optional error={fields.notes}>
        {(p) => <Textarea {...p} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder={collecting ? "Anything about the payment" : "What happened, and what's next"} />}
      </Field>
      <FormError message={error} />
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" variant="primary" loading={pending} disabled={!companyId}>
          {collecting ? "Log collection" : "Log visit"}
        </Button>
        <p className="text-meta text-ink-3">{requireLocation ? "Where you are now is saved with the visit (required)." : "Where you are now is saved with the visit."}</p>
      </div>
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
  requireLocation?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  return (
    <>
      <Button variant={variant} icon={<MapPin className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
        {label}
      </Button>
      <Modal open={open} title={form.doctor ? `Visit to ${form.doctor.name}` : "Log visit"} onCancel={() => setOpen(false)} footer={null} width={560}>
          <LogVisitForm
            {...form}
            onDone={() => {
              setOpen(false);
              router.refresh();
            }}
          />
      </Modal>
    </>
  );
}
