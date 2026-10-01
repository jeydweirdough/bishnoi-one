"use client";

import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { receivePrescription, updatePrescription, type ItemInput } from "../actions/pharmacy";
import type { Prescription } from "../lib/types";

type PatientOption = { id: string; fullName: string; birthDate: string | null; kind: string };
type MedicineOption = { id: string; label: string };
type Row = { writtenAs: string; medicineId: string; quantity: string; directions: string };

const blankRow = (): Row => ({ writtenAs: "", medicineId: "", quantity: "", directions: "" });

/**
 * Taking a prescription in, or correcting one before it's verified. What's
 * entered is what the prescriber wrote; matching it to the catalogue is part
 * of checking it, so the medicine is optional here.
 */
export function PrescriptionForm({
  patients,
  medicines,
  rx,
  today,
  canAddPatients,
  presetPatientId,
}: {
  patients: PatientOption[];
  medicines: MedicineOption[];
  rx?: Prescription;
  today: string;
  canAddPatients: boolean;
  presetPatientId?: string;
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [who, setWho] = useState<"existing" | "new">("existing");
  const [patientId, setPatientId] = useState(rx?.patient.id ?? presetPatientId ?? "");
  const [find, setFind] = useState("");
  const [newPatient, setNewPatient] = useState({ fullName: "", birthDate: "", phone: "", allergies: "" });
  const [prescriber, setPrescriber] = useState({
    name: rx?.prescriberName ?? "",
    license: rx?.prescriberLicense ?? "",
    clinic: rx?.prescriberClinic ?? "",
    on: rx?.prescribedOn ?? today,
  });
  const [notes, setNotes] = useState(rx?.notes ?? "");
  const [rows, setRows] = useState<Row[]>(
    rx ? rx.items.map((i) => ({ writtenAs: i.writtenAs, medicineId: i.medicine?.id ?? "", quantity: String(i.quantity), directions: i.directions ?? "" })) : [blankRow()],
  );
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  const needle = find.trim().toLowerCase();
  const shown = needle ? patients.filter((p) => p.fullName.toLowerCase().includes(needle)).slice(0, 50) : patients.slice(0, 50);
  const chosen = patients.find((p) => p.id === patientId);

  function setRow(n: number, change: Partial<Row>) {
    setRows(rows.map((r, i) => (i === n ? { ...r, ...change } : r)));
  }

  function submit() {
    const items: ItemInput[] = rows.map((r) => ({
      writtenAs: r.writtenAs.trim(),
      medicineId: r.medicineId || null,
      quantity: Number.parseInt(r.quantity, 10) || 0,
      directions: r.directions.trim() || null,
    }));
    const details = {
      prescriberName: prescriber.name.trim(),
      prescriberLicense: prescriber.license.trim() || null,
      prescriberClinic: prescriber.clinic.trim() || null,
      prescribedOn: prescriber.on,
      notes: notes.trim() || null,
      items,
    };
    start(async () => {
      const result = rx
        ? await updatePrescription(rx.id, details)
        : await receivePrescription({
            ...details,
            patientId: who === "existing" ? patientId || null : null,
            newPatient:
              who === "new"
                ? {
                    fullName: newPatient.fullName.trim(),
                    birthDate: newPatient.birthDate || null,
                    phone: newPatient.phone.trim() || null,
                    allergies: newPatient.allergies.trim() || null,
                  }
                : null,
          });
      if (result.ok) {
        toast.success(rx ? "Prescription corrected" : "Prescription received: it's in the inbox", { description: result.data.number });
        router.push(`/prescriptions/${result.data.id}`);
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
      className="space-y-8"
    >
      {!rx && (
        <fieldset className="space-y-4">
          <legend className="mb-2 text-heading text-ink">Patient</legend>
          {canAddPatients && (
            <Choice
              name="who"
              legend="Who is it for?"
              value={who}
              onChange={setWho}
              options={[
                { value: "existing", label: "Someone on record" },
                { value: "new", label: "A new patient" },
              ]}
            />
          )}
          {who === "existing" ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Find" hint={chosen ? `Chosen: ${chosen.fullName}` : "Type part of their name."}>
                {(p) => <Input {...p} value={find} onChange={(e) => setFind(e.target.value)} placeholder="Name" autoComplete="off" />}
              </Field>
              <Field label="Patient" error={fields.patientId}>
                {(p) => (
                  <Select {...p} value={patientId} onChange={(e) => setPatientId(e.target.value)}>
                    <option value="">Pick someone</option>
                    {chosen && !shown.includes(chosen) && <option value={chosen.id}>{chosen.fullName}</option>}
                    {shown.map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.fullName}
                        {x.birthDate ? ` · born ${x.birthDate}` : ""}
                        {x.kind === "customer" ? " · customer" : ""}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Full name" error={fields.fullName}>
                {(p) => <Input {...p} value={newPatient.fullName} onChange={(e) => setNewPatient({ ...newPatient, fullName: e.target.value })} required />}
              </Field>
              <Field label="Date of birth" optional error={fields.birthDate}>
                {(p) => <Input {...p} type="date" max={today} value={newPatient.birthDate} onChange={(e) => setNewPatient({ ...newPatient, birthDate: e.target.value })} />}
              </Field>
              <Field label="Phone" optional>
                {(p) => <Input {...p} type="tel" value={newPatient.phone} onChange={(e) => setNewPatient({ ...newPatient, phone: e.target.value })} />}
              </Field>
              <Field label="Allergies" optional hint="Shown on every check.">
                {(p) => <Input {...p} value={newPatient.allergies} onChange={(e) => setNewPatient({ ...newPatient, allergies: e.target.value })} />}
              </Field>
            </div>
          )}
        </fieldset>
      )}

      <fieldset className="space-y-4">
        <legend className="mb-2 text-heading text-ink">Prescriber</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Prescriber" error={fields.prescriberName}>
            {(p) => <Input {...p} value={prescriber.name} onChange={(e) => setPrescriber({ ...prescriber, name: e.target.value })} placeholder="Dr. …" required />}
          </Field>
          <Field label="Licence no." optional hint="Required for dangerous drugs." error={fields.prescriberLicense}>
            {(p) => <Input {...p} value={prescriber.license} onChange={(e) => setPrescriber({ ...prescriber, license: e.target.value })} />}
          </Field>
          <Field label="Clinic or hospital" optional>
            {(p) => <Input {...p} value={prescriber.clinic} onChange={(e) => setPrescriber({ ...prescriber, clinic: e.target.value })} />}
          </Field>
          <Field label="Prescription date" error={fields.prescribedOn}>
            {(p) => <Input {...p} type="date" value={prescriber.on} onChange={(e) => setPrescriber({ ...prescriber, on: e.target.value })} required />}
          </Field>
        </div>
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="mb-2 text-heading text-ink">Medicines, as written</legend>
        {rows.map((row, n) => (
          <div key={n} className="grid gap-3 rounded-[3px] border border-rule p-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,2fr)_6rem_auto]">
            <Field label="Written as" error={fields[`items.${n}.writtenAs`]}>
              {(p) => <Input {...p} value={row.writtenAs} onChange={(e) => setRow(n, { writtenAs: e.target.value })} placeholder="Amoxicillin 500mg cap" />}
            </Field>
            <Field label="Catalogue medicine" optional error={fields[`items.${n}.medicineId`]}>
              {(p) => (
                <Select {...p} value={row.medicineId} onChange={(e) => setRow(n, { medicineId: e.target.value })}>
                  <option value="">Match when checking</option>
                  {medicines.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Quantity" error={fields[`items.${n}.quantity`]}>
              {(p) => <Input {...p} inputMode="numeric" value={row.quantity} onChange={(e) => setRow(n, { quantity: e.target.value.replace(/\D/g, "") })} />}
            </Field>
            <div className="flex items-end">
              <Button
                size="sm"
                variant="quiet"
                disabled={rows.length === 1}
                onClick={() => setRows(rows.filter((_, i) => i !== n))}
                title="Remove this medicine"
                aria-label={`Remove medicine ${n + 1}`}
                icon={<Trash2 className="size-4" aria-hidden />}
              />
            </div>
            <Field label="Directions" optional className="sm:col-span-4">
              {(p) => <Input {...p} value={row.directions} onChange={(e) => setRow(n, { directions: e.target.value })} placeholder="1 capsule 3 times a day for 7 days" />}
            </Field>
          </div>
        ))}
        {fields.items && <p className="text-meta text-danger">{fields.items}</p>}
        <Button size="sm" onClick={() => setRows([...rows, blankRow()])} icon={<Plus className="size-4" aria-hidden />} disabled={rows.length >= 30}>
          Add a medicine
        </Button>
      </fieldset>

      <Field label="Notes" optional>
        {(p) => <Textarea {...p} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={4000} />}
      </Field>

      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {rx ? "Save corrections" : "Receive prescription"}
        </Button>
        <LinkButton href={rx ? `/prescriptions/${rx.id}` : "/prescriptions"} variant="quiet">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}
