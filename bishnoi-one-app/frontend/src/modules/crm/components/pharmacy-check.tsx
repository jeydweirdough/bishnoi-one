"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { sendToPharmacy } from "@/src/modules/crm/actions/quote-pharmacy";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, FormGrid, Input, Textarea } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org, Quote } from "@/src/platform/lib/types";

/** Sends an Rx quote to Bishnoi One Pharmacy with the prescription's details, or
 *  sends it again once they're corrected. Sits in the quote's Pharmacist check
 *  section; the verdict comes back there. */
export function PharmacyCheckForm({ quote, org, linked }: { quote: Quote; org: Org; linked: boolean }) {
  const check = quote.pharmacy;
  const [open, setOpen] = useState(check?.outcome === "needs_clarification");
  if (!check || !quote.can.sendToPharmacy) return null;
  if (!linked) {
    return (
      <p className="mt-2 text-meta text-ink-3">
        Pharmacy isn&apos;t connected yet. Your administrator sets PHARMACY_API_URL and PHARMACY_API_KEY.
      </p>
    );
  }
  const again = check.outcome !== "not_sent";
  if (!open) {
    return (
      <Button size="sm" variant={again ? "default" : "primary"} className="mt-3" onClick={() => setOpen(true)}>
        {again ? "Correct and send again" : "Send to Pharmacy"}
      </Button>
    );
  }
  return <DetailsForm quote={quote} org={org} again={again} onDone={() => setOpen(false)} />;
}

function DetailsForm({ quote, org, again, onDone }: { quote: Quote; org: Org; again: boolean; onDone: () => void }) {
  const fmt = makeFormat(org);
  const today = fmt.todayKey();
  const sent = quote.pharmacy?.sent;
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const text = (name: string) => String(data.get(name) ?? "").trim();
    const input = {
      prescriberName: text("prescriberName"),
      prescriberLicense: text("prescriberLicense") || null,
      prescriberClinic: text("prescriberClinic") || null,
      prescribedOn: text("prescribedOn"),
      notes: text("notes") || null,
    };
    const missing: Record<string, string> = {};
    if (!input.prescriberName) missing.prescriberName = "Enter the prescriber's name.";
    if (!input.prescribedOn) missing.prescribedOn = "Enter the date on the prescription.";
    if (Object.keys(missing).length) {
      setFields(missing);
      return;
    }
    start(async () => {
      const result = await sendToPharmacy(quote.id, input);
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(`${quote.number} sent to Pharmacy`, { description: "A pharmacist checks it before it can be ordered." });
      setError(null);
      setFields({});
      onDone();
    });
  }

  return (
    <form onSubmit={submit} noValidate className="mt-3 space-y-3">
      <p className="text-meta font-semibold text-ink-2">The prescription</p>
      <Field label="Prescriber" error={fields.prescriberName}>
        {(p) => <Input {...p} name="prescriberName" maxLength={120} defaultValue={sent?.prescriberName} placeholder="Dr. Elena Ramos" />}
      </Field>
      <FormGrid>
        <Field label="Licence number" size="lg" optional error={fields.prescriberLicense}>
          {(p) => <Input {...p} name="prescriberLicense" maxLength={40} defaultValue={sent?.prescriberLicense ?? ""} />}
        </Field>
        <Field label="Prescribed on" size="sm" error={fields.prescribedOn}>
          {(p) => <Input {...p} name="prescribedOn" type="date" max={today} defaultValue={sent?.prescribedOn ?? ""} />}
        </Field>
      </FormGrid>
      <Field label="Clinic or hospital" optional error={fields.prescriberClinic}>
        {(p) => <Input {...p} name="prescriberClinic" maxLength={160} defaultValue={sent?.prescriberClinic ?? ""} />}
      </Field>
      <Field label="Notes for the pharmacist" optional error={fields.notes}>
        {(p) => <Textarea {...p} name="notes" rows={2} maxLength={4000} defaultValue={sent?.notes ?? ""} />}
      </Field>
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" size="sm" variant="primary" loading={pending}>
          {again ? "Send again" : "Send to Pharmacy"}
        </Button>
        <Button type="button" size="sm" variant="quiet" onClick={onDone} disabled={pending}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
