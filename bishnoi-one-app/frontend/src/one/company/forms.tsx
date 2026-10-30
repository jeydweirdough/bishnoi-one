"use client";

import { LogOut, UserMinus, UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormGrid, Input } from "@/src/platform/ui/field";
import { Combobox, Select } from "@/src/platform/ui/pickers";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { changeCompany, setAdministrator, signPersonOut } from "./actions";
import type { Administrators, CompanyProfile } from "./types";

const ZONES = ["Asia/Manila", "Asia/Singapore", "Asia/Hong_Kong", "Asia/Tokyo", "Asia/Dubai", "Europe/London", "America/New_York", "America/Los_Angeles", "UTC"];
const CURRENCIES = [
  { value: "PHP", label: "PHP · Philippine peso" },
  { value: "USD", label: "USD · US dollar" },
  { value: "SGD", label: "SGD · Singapore dollar" },
  { value: "EUR", label: "EUR · Euro" },
];

/** The company's name, contact email, email domain, time zone and currency: saved together. */
export function ProfileForm({ company }: { company: CompanyProfile }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [form, setForm] = useState({ name: company.name, contactEmail: company.contactEmail ?? "", emailDomain: company.emailDomain ?? "", timezone: company.timezone, currency: company.currency });
  const dirty =
    form.name !== company.name || form.contactEmail !== (company.contactEmail ?? "") || form.emailDomain !== (company.emailDomain ?? "") ||
    form.timezone !== company.timezone || form.currency !== company.currency;

  function save() {
    start(async () => {
      const r = await changeCompany({ ...form, name: form.name.trim(), contactEmail: form.contactEmail.trim() || null, emailDomain: form.emailDomain.trim() });
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
      <Field label="Email domain" size="md" optional error={errors.emailDomain} hint="Your people are added and sign in with emails at it, such as getmeds.ph. Public ones (gmail.com) can't be used.">
        {(p) => <Input {...p} prefix="@" value={form.emailDomain} onChange={(e) => setForm({ ...form, emailDomain: e.target.value })} maxLength={253} placeholder="getmeds.ph" />}
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

/** The letterhead every printed document carries (step 10): legal name, address, TIN, phone, logo and footer. */
export function LetterheadForm({ company }: { company: CompanyProfile }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const first = { legalName: company.legalName ?? "", address: company.address ?? "", tin: company.tin ?? "", phone: company.phone ?? "", documentFooter: company.documentFooter ?? "" };
  const [form, setForm] = useState(first);
  const [logo, setLogo] = useState<string | null | undefined>(undefined); // undefined: unchanged; null: removed
  const dirty = JSON.stringify(form) !== JSON.stringify(first) || logo !== undefined;
  const shown = logo === undefined ? company.logo : logo;

  function pick(file: File | undefined) {
    if (!file) return;
    if (!["image/png", "image/jpeg"].includes(file.type)) return void toast.error("Use a PNG or JPEG image.");
    if (file.size > 400_000) return void toast.error("Keep the logo under 400 KB.");
    const reader = new FileReader();
    reader.onload = () => setLogo(String(reader.result));
    reader.readAsDataURL(file);
  }

  function save() {
    start(async () => {
      const r = await changeCompany({ ...form, ...(logo !== undefined ? { logo: logo ?? "" } : {}) });
      if (!r.ok) {
        setErrors("fields" in r && r.fields ? r.fields : {});
        return void toast.error(r.error);
      }
      setErrors({});
      setLogo(undefined);
      toast.success("Letterhead saved", { description: "Every printed document uses it from now on." });
      router.refresh();
    });
  }

  return (
    <FormGrid>
      <Field label="Legal name" size="md" optional error={errors.legalName} hint="As registered; printed at the top.">
        {(p) => <Input {...p} value={form.legalName} onChange={(e) => setForm({ ...form, legalName: e.target.value })} maxLength={200} placeholder={company.name} />}
      </Field>
      <Field label="TIN" size="md" optional error={errors.tin}>
        {(p) => <Input {...p} value={form.tin} onChange={(e) => setForm({ ...form, tin: e.target.value })} maxLength={30} placeholder="000-000-000-000" />}
      </Field>
      <Field label="Address" size="full" optional error={errors.address}>
        {(p) => <Input {...p} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} maxLength={400} />}
      </Field>
      <Field label="Phone" size="md" optional error={errors.phone}>
        {(p) => <Input {...p} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} maxLength={40} />}
      </Field>
      <Field label="Footer" size="md" optional error={errors.documentFooter} hint="A line at the foot of every document.">
        {(p) => <Input {...p} value={form.documentFooter} onChange={(e) => setForm({ ...form, documentFooter: e.target.value })} maxLength={400} />}
      </Field>
      <div className="sm:col-span-6">
        <p className="mb-1.5 text-sm font-medium text-ink">Logo</p>
        <div className="flex flex-wrap items-center gap-3">
          {shown ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={shown} alt="Company logo" className="h-14 max-w-48 rounded border border-rule bg-white object-contain p-1" />
          ) : (
            <span className="text-meta text-ink-3">No logo yet</span>
          )}
          <label className="cursor-pointer rounded-lg border border-rule-strong bg-sheet px-3 py-1.5 text-sm text-ink hover:border-hema">
            {shown ? "Change" : "Upload"}
            <input suppressHydrationWarning type="file" accept="image/png,image/jpeg" className="sr-only" onChange={(e) => pick(e.target.files?.[0])} />
          </label>
          {shown && (
            <Button size="sm" variant="quiet" onClick={() => setLogo(null)}>
              Remove
            </Button>
          )}
          {errors.logo && <span className="text-meta text-danger">{errors.logo}</span>}
        </div>
      </div>
      <div className="sm:col-span-6">
        <Button variant="primary" onClick={save} loading={busy} disabled={!dirty}>
          Save letterhead
        </Button>
      </div>
    </FormGrid>
  );
}

/** Who runs the company in Bishnoi One (2026-10-30): add one from the company's people, remove one
 * beside their name. Never yourself, never the last one (the Platform refuses both). */
export function AdministratorsCard({ data }: { data: Administrators }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [pick, setPick] = useState<string | undefined>(undefined);
  const only = data.administrators.length === 1;

  function add() {
    if (!pick) return;
    start(async () => {
      const r = await setAdministrator(pick, true);
      if (!r.ok) return void toast.error(r.error);
      const p = data.others.find((o) => o.id === pick);
      toast.success(`${p?.fullName ?? "They"} can now run the company`, { description: "They see the Admin Console from their next page." });
      setPick(undefined);
      router.refresh();
    });
  }

  return (
    <div className="space-y-3">
      <ul className="divide-y divide-rule">
        {data.administrators.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
            <span className="font-medium text-ink">{a.fullName}</span>
            <span className="text-ink-3">{a.email}</span>
            {a.isMe && <span className="text-meta text-ink-3">(you)</span>}
            <span className="ml-auto">
              {!a.isMe && !only && (
                <ConfirmButton
                  label="Remove"
                  triggerSize="sm"
                  icon={<UserMinus className="size-4" aria-hidden />}
                  title={`Remove ${a.fullName} as administrator?`}
                  body="They keep their apps and role, but can no longer open the Admin Console or change the company. Their sign-ins end; they sign in again."
                  confirmLabel="Remove"
                  onConfirm={async () => {
                    const r = await setAdministrator(a.id, false);
                    if (!r.ok) {
                      toast.error(r.error);
                      return false;
                    }
                    toast.success(`${a.fullName} is no longer an administrator`);
                    router.refresh();
                  }}
                />
              )}
            </span>
          </li>
        ))}
      </ul>
      {only && <p className="text-meta text-ink-3">To replace the only administrator, add the new one first, then remove the old one.</p>}
      {data.others.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-56 flex-1">
            <Combobox
              aria-label="Person to make an administrator"
              placeholder="Choose a person"
              value={pick}
              onChange={(v) => setPick(v as string)}
              options={data.others.map((o) => ({ value: o.id, label: `${o.fullName} · ${o.email}` }))}
            />
          </div>
          <Button icon={<UserPlus className="size-4" aria-hidden />} onClick={add} loading={busy} disabled={!pick}>
            Make administrator
          </Button>
        </div>
      ) : (
        <p className="text-meta text-ink-3">Everyone here is already an administrator. Add people on People first.</p>
      )}
    </div>
  );
}
