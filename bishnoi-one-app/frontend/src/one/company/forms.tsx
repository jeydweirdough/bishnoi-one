"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormGrid, Input } from "@/src/platform/ui/field";
import { Combobox, Select } from "@/src/platform/ui/pickers";
import { changeCompany, signPersonOut } from "./actions";
import type { CompanyProfile } from "./types";

const ZONES = ["Asia/Manila", "Asia/Singapore", "Asia/Hong_Kong", "Asia/Tokyo", "Asia/Dubai", "Europe/London", "America/New_York", "America/Los_Angeles", "UTC"];
const CURRENCIES = [
  { value: "PHP", label: "PHP · Philippine peso" },
  { value: "USD", label: "USD · US dollar" },
  { value: "SGD", label: "SGD · Singapore dollar" },
  { value: "EUR", label: "EUR · Euro" },
];

/** The company's name, contact email, time zone and currency: saved together. */
export function ProfileForm({ company }: { company: CompanyProfile }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [form, setForm] = useState({ name: company.name, contactEmail: company.contactEmail ?? "", timezone: company.timezone, currency: company.currency });
  const dirty = form.name !== company.name || form.contactEmail !== (company.contactEmail ?? "") || form.timezone !== company.timezone || form.currency !== company.currency;

  function save() {
    start(async () => {
      const r = await changeCompany({ ...form, name: form.name.trim(), contactEmail: form.contactEmail.trim() || null });
      if (!r.ok) {
        setErrors("fields" in r && r.fields ? r.fields : {});
        return void toast.error(r.error);
      }
      setErrors({});
      toast.success("Saved", { description: "Every app is told at once." });
      router.refresh();
    });
  }

  const zones = ZONES.includes(company.timezone) ? ZONES : [company.timezone, ...ZONES];
  return (
    <FormGrid>
      <Field label="Company name" size="md" error={errors.name}>
        {(p) => <Input {...p} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={120} />}
      </Field>
      <Field label="Contact email" size="md" optional error={errors.contactEmail} hint="Where Bishnoi One writes to the company.">
        {(p) => <Input {...p} type="email" value={form.contactEmail} onChange={(e) => setForm({ ...form, contactEmail: e.target.value })} maxLength={254} />}
      </Field>
      <Field label="Time zone" size="md" error={errors.timezone}>
        {(p) => (
          <Select {...p} value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })}>
            {zones.map((z) => (
              <option key={z} value={z}>
                {z.replace("_", " ")}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label="Currency" size="md" error={errors.currency}>
        {() => <Combobox options={CURRENCIES} value={form.currency} onChange={(v) => setForm({ ...form, currency: String(v) })} />}
      </Field>
      <div className="sm:col-span-6">
        <Button variant="primary" onClick={save} loading={busy} disabled={!dirty}>
          Save
        </Button>
      </div>
    </FormGrid>
  );
}

/** Ends a person's open sign-ins, beside their name. */
export function SignOutButton({ id, name, count }: { id: string; name: string; count: number }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  if (count === 0) return null;
  return (
    <Button
      size="sm"
      icon={<LogOut className="size-4" aria-hidden />}
      loading={busy}
      onClick={() =>
        start(async () => {
          const r = await signPersonOut(id);
          if (!r.ok) return void toast.error(r.error);
          toast.success(`${name} is signed out`, { description: "They sign in again on their next step." });
          router.refresh();
        })
      }
    >
      Sign out
    </Button>
  );
}
