"use client";

import { KeyRound, Pencil } from "lucide-react";
import { Modal } from "@/src/modules/admin/platform/ui/modal";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { changePassword } from "@/src/one/actions";
import { Button } from "@/src/modules/admin/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/modules/admin/platform/ui/field";
import { saveProfile, type Profile } from "@/src/modules/admin/platform/actions/account";

// The profile's own buttons, beside the picture: editing one's details, and
// changing one's password. Role and team stay an admin's to set.

export function ProfileActions({ profile, today }: { profile: Profile; today: string }) {
  const [editing, setEditing] = useState(false);
  const [password, setPassword] = useState(false);
  return (
    <div className="flex flex-wrap gap-2">
      <Button icon={<KeyRound className="size-4" aria-hidden />} onClick={() => setPassword(true)}>
        Change password
      </Button>
      <Button variant="primary" icon={<Pencil className="size-4" aria-hidden />} onClick={() => setEditing(true)}>
        Edit profile
      </Button>
      {editing && <EditProfile profile={profile} today={today} onClose={() => setEditing(false)} />}
      {password && <ChangePassword onClose={() => setPassword(false)} />}
    </div>
  );
}

const GENDERS = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "other", label: "Other" },
];

function EditProfile({ profile, today, onClose }: { profile: Profile; today: string; onClose: () => void }) {
  const router = useRouter();
  const [form, setForm] = useState({
    firstName: profile.firstName,
    middleInitial: profile.middleInitial ?? "",
    lastName: profile.lastName,
    suffix: profile.suffix ?? "",
    gender: profile.gender ?? "",
    phone: profile.phone ?? "",
    email: profile.email,
    birthday: profile.birthday ?? "",
    currentPassword: "",
  });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }));
  const emailChanged = form.email.trim().toLowerCase() !== profile.email.toLowerCase();

  function save() {
    // What the API would say anyway, said before it's asked.
    const missing: Record<string, string> = {};
    if (!form.firstName.trim()) missing.firstName = "Enter your first name.";
    if (!form.lastName.trim()) missing.lastName = "Enter your last name.";
    if (!form.gender) missing.gender = "Select a gender.";
    if (!form.phone.trim()) missing.phone = "Enter a contact number.";
    if (!form.email.trim()) missing.email = "Enter your email.";
    if (emailChanged && !form.currentPassword) missing.currentPassword = "Enter your current password to change your email.";
    setFields(missing);
    setError(null);
    if (Object.keys(missing).length) return;
    start(async () => {
      const r = await saveProfile({
        ...form,
        middleInitial: form.middleInitial || null,
        suffix: form.suffix || null,
        birthday: form.birthday || null,
        currentPassword: emailChanged ? form.currentPassword : undefined,
      });
      if (!r.ok) {
        setFields(r.fields ?? {});
        setError(r.fields && Object.keys(r.fields).length ? null : r.error);
        return;
      }
      toast.success("Profile saved");
      onClose();
      router.refresh();
    });
  }

  return (
    <Modal
      open
      title="Edit profile"
      onCancel={() => !saving && onClose()}
      onOk={save}
      okText="Save"
      cancelText="Cancel"
      confirmLoading={saving}
      width={600}
     
    >
      <form
        className="mt-3 grid gap-4 sm:grid-cols-6"
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
      >
        <Field label="First name" error={fields.firstName} className="sm:col-span-3">
          {(p) => <Input {...p} value={form.firstName} onChange={(e) => set("firstName")(e.target.value)} autoComplete="given-name" maxLength={60} autoFocus />}
        </Field>
        <Field label="Middle initial" optional error={fields.middleInitial} className="sm:col-span-1">
          {(p) => <Input {...p} value={form.middleInitial} onChange={(e) => set("middleInitial")(e.target.value)} maxLength={3} placeholder="M" />}
        </Field>
        <Field label="Suffix" optional error={fields.suffix} className="sm:col-span-2">
          {(p) => <Input {...p} value={form.suffix} onChange={(e) => set("suffix")(e.target.value)} maxLength={10} placeholder="Jr., Sr., III" autoComplete="honorific-suffix" />}
        </Field>
        <Field label="Last name" error={fields.lastName} className="sm:col-span-6">
          {(p) => <Input {...p} value={form.lastName} onChange={(e) => set("lastName")(e.target.value)} autoComplete="family-name" maxLength={60} />}
        </Field>
        <Field label="Gender" error={fields.gender} className="sm:col-span-3">
          {(p) => (
            <Select {...p} value={form.gender} onChange={(e) => set("gender")(e.target.value)}>
              <option value="" disabled>
                Select
              </option>
              {GENDERS.map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Birthday" optional error={fields.birthday} className="sm:col-span-3">
          {(p) => <Input {...p} type="date" value={form.birthday} max={today} onChange={(e) => set("birthday")(e.target.value)} />}
        </Field>
        <Field label="Contact number" error={fields.phone} className="sm:col-span-3">
          {(p) => <Input {...p} type="tel" value={form.phone} onChange={(e) => set("phone")(e.target.value)} autoComplete="tel" placeholder="+63 917 123 4567" maxLength={20} />}
        </Field>
        <Field label="Email" error={fields.email} hint={emailChanged ? "You'll sign in with this one from now on." : undefined} className="sm:col-span-3">
          {(p) => <Input {...p} type="email" value={form.email} onChange={(e) => set("email")(e.target.value)} autoComplete="email" maxLength={254} />}
        </Field>
        {emailChanged && (
          <Field label="Current password" error={fields.currentPassword} hint="Your email is how you sign in, so changing it asks for your password." className="sm:col-span-6">
            {(p) => <Input {...p} type="password" value={form.currentPassword} onChange={(e) => set("currentPassword")(e.target.value)} autoComplete="current-password" />}
          </Field>
        )}
        <p className="text-meta text-ink-3 sm:col-span-6">Your role and team are set by an admin.</p>
        <div className="sm:col-span-6">
          <FormError message={error} />
        </div>
        <button suppressHydrationWarning type="submit" hidden />
      </form>
    </Modal>
  );
}

function ChangePassword({ onClose }: { onClose: () => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();

  function save() {
    const missing: Record<string, string> = {};
    if (!current) missing.currentPassword = "Enter your current password.";
    if (!next) missing.newPassword = "Enter a new password.";
    else if (next !== again) missing.again = "The two new passwords aren't the same.";
    setFields(missing);
    setError(null);
    if (Object.keys(missing).length) return;
    start(async () => {
      const r = await changePassword(current, next);
      if (!r.ok) {
        const f = "fields" in r ? (r.fields ?? {}) : {};
        setFields(f);
        setError(Object.keys(f).length ? null : r.error);
        return;
      }
      toast.success("Password changed", { description: "You're still signed in here; everywhere else you'll sign in with the new one." });
      onClose();
    });
  }

  return (
    <Modal open title="Change password" onCancel={() => !saving && onClose()} onOk={save} okText="Change password" cancelText="Cancel" confirmLoading={saving} width={440}>
      <form
        className="mt-3 space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
      >
        <Field label="Current password" error={fields.currentPassword}>
          {(p) => <Input {...p} type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" autoFocus />}
        </Field>
        <Field label="New password" error={fields.newPassword} hint="At least 8 characters. A short phrase is easier to remember.">
          {(p) => <Input {...p} type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" />}
        </Field>
        <Field label="New password again" error={fields.again}>
          {(p) => <Input {...p} type="password" value={again} onChange={(e) => setAgain(e.target.value)} autoComplete="new-password" />}
        </Field>
        <p className="text-meta text-ink-3">Every other place you're signed in will ask for the new password.</p>
        <FormError message={error} />
        <button suppressHydrationWarning type="submit" hidden />
      </form>
    </Modal>
  );
}
