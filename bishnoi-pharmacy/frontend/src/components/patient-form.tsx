"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { createPatient, updatePatient, type PatientInput } from "../actions/pharmacy";
import type { Patient, PersonKind } from "../lib/types";

/** A patient or customer: who they are, how to reach them, and their allergies. */
export function PatientForm({ patient, today, kind = "patient", canEdit = true }: { patient?: Patient; today: string; kind?: PersonKind; canEdit?: boolean }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [v, setV] = useState({
    kind: patient?.kind ?? kind,
    fullName: patient?.fullName ?? "",
    birthDate: patient?.birthDate ?? "",
    sex: patient?.sex ?? "",
    phone: patient?.phone ?? "",
    email: patient?.email ?? "",
    address: patient?.address ?? "",
    allergies: patient?.allergies ?? "",
    notes: patient?.notes ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const set = (change: Partial<typeof v>) => setV({ ...v, ...change });

  function submit() {
    const input: PatientInput = {
      kind: v.kind,
      fullName: v.fullName.trim(),
      birthDate: v.birthDate || null,
      sex: (v.sex || null) as PatientInput["sex"],
      phone: v.phone.trim() || null,
      email: v.email.trim() || null,
      address: v.address.trim() || null,
      allergies: v.allergies.trim() || null,
      notes: v.notes.trim() || null,
    };
    start(async () => {
      const result = patient ? await updatePatient(patient.id, input) : await createPatient(input);
      if (result.ok) {
        toast.success(patient ? "Changes saved" : `${input.kind === "patient" ? "Patient" : "Customer"} added`, { description: result.data.fullName });
        setError(null);
        setFields({});
        if (!patient) router.push(`/patients/${result.data.id}`);
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
      <fieldset disabled={!canEdit} className="grid gap-5 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Choice
            name="kind"
            legend="Kind"
            value={v.kind}
            onChange={(k) => set({ kind: k })}
            options={[
              { value: "patient", label: "Patient: has prescriptions dispensed" },
              { value: "customer", label: "Customer: buys over the counter" },
            ]}
          />
        </div>
        <Field label="Full name" error={fields.fullName}>
          {(p) => <Input {...p} value={v.fullName} onChange={(e) => set({ fullName: e.target.value })} required autoFocus={!patient} />}
        </Field>
        <Field label="Date of birth" optional error={fields.birthDate}>
          {(p) => <Input {...p} type="date" max={today} value={v.birthDate} onChange={(e) => set({ birthDate: e.target.value })} />}
        </Field>
        <Field label="Sex" optional>
          {(p) => (
            <Select {...p} value={v.sex} onChange={(e) => set({ sex: e.target.value })}>
              <option value="">Not given</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
            </Select>
          )}
        </Field>
        <Field label="Phone" optional error={fields.phone}>
          {(p) => <Input {...p} type="tel" value={v.phone} onChange={(e) => set({ phone: e.target.value })} />}
        </Field>
        <Field label="Email" optional error={fields.email}>
          {(p) => <Input {...p} type="email" value={v.email} onChange={(e) => set({ email: e.target.value })} />}
        </Field>
        <Field label="Address" optional>
          {(p) => <Input {...p} value={v.address} onChange={(e) => set({ address: e.target.value })} />}
        </Field>
        <Field label="Allergies" optional className="sm:col-span-2" hint="Shown on every prescription check and at dispensing.">
          {(p) => <Input {...p} value={v.allergies} onChange={(e) => set({ allergies: e.target.value })} placeholder="Penicillin, sulfa drugs…" />}
        </Field>
        <Field label="Notes" optional className="sm:col-span-2">
          {(p) => <Textarea {...p} value={v.notes} onChange={(e) => set({ notes: e.target.value })} maxLength={4000} />}
        </Field>
      </fieldset>
      <FormError message={error} />
      {canEdit && (
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant="primary" loading={pending}>
            {patient ? "Save changes" : "Add"}
          </Button>
          <LinkButton href="/patients" variant="quiet">
            {patient ? "Back to the list" : "Cancel"}
          </LinkButton>
        </div>
      )}
    </form>
  );
}
