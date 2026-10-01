"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { createUser, resetPassword, updateUser, type UserChange } from "../actions/pharmacy";
import type { AdminUser, RoleOption } from "../lib/types";

/** Adding a person or changing one: name, email, role, and a pharmacist's licence number. */
export function UserForm({ roles, user, isMe }: { roles: RoleOption[]; user?: AdminUser; isMe?: boolean }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [v, setV] = useState({
    fullName: user?.fullName ?? "",
    email: user?.email ?? "",
    roleId: user?.role.id ?? roles.find((r) => r.name === "Pharmacy Assistant")?.id ?? roles[0]?.id ?? "",
    licenseNo: user?.licenseNo ?? "",
    password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const set = (change: Partial<typeof v>) => setV({ ...v, ...change });
  const role = roles.find((r) => r.id === v.roleId);

  function finish(result: Awaited<ReturnType<typeof updateUser>>, message: string) {
    if (result.ok) {
      toast.success(message, { description: result.data.fullName });
      setError(null);
      setFields({});
      if (!user) router.push(`/admin/users/${result.data.id}`);
      router.refresh();
      return;
    }
    setError(result.error);
    setFields(result.fields ?? {});
  }

  function submit() {
    start(async () => {
      if (!user) {
        finish(await createUser({ fullName: v.fullName.trim(), email: v.email.trim(), roleId: v.roleId, licenseNo: v.licenseNo.trim() || null, password: v.password }), "Person added");
        return;
      }
      const change: UserChange = {};
      if (v.fullName.trim() !== user.fullName) change.fullName = v.fullName.trim();
      if (v.email.trim().toLowerCase() !== user.email) change.email = v.email.trim();
      if (v.roleId !== user.role.id) change.roleId = v.roleId;
      if ((v.licenseNo.trim() || null) !== user.licenseNo) change.licenseNo = v.licenseNo.trim() || null;
      if (Object.keys(change).length === 0) return void toast("Nothing changed");
      finish(await updateUser(user.id, change), "Changes saved");
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
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Full name" error={fields.fullName}>
          {(p) => <Input {...p} value={v.fullName} onChange={(e) => set({ fullName: e.target.value })} required autoFocus={!user} />}
        </Field>
        <Field label="Work email" error={fields.email} hint={user ? undefined : "They sign in with this."}>
          {(p) => <Input {...p} type="email" value={v.email} onChange={(e) => set({ email: e.target.value })} required />}
        </Field>
        <Field label="Role" error={fields.roleId} hint={role?.description ?? undefined}>
          {(p) => (
            <Select {...p} value={v.roleId} onChange={(e) => set({ roleId: e.target.value })}>
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Licence no." optional error={fields.licenseNo} hint="A pharmacist's PRC number, shown beside what they verify and dispense.">
          {(p) => <Input {...p} value={v.licenseNo} onChange={(e) => set({ licenseNo: e.target.value })} />}
        </Field>
        {!user && (
          <Field label="First password" error={fields.password} hint="At least 8 characters. Give it to them yourself.">
            {(p) => <Input {...p} type="password" value={v.password} onChange={(e) => set({ password: e.target.value })} autoComplete="new-password" />}
          </Field>
        )}
      </div>
      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {user ? "Save changes" : "Add person"}
        </Button>
        {user && !isMe && (
          <Button
            disabled={pending}
            onClick={() => start(async () => finish(await updateUser(user.id, { isActive: !user.isActive }), user.isActive ? "Switched off" : "Switched on"))}
          >
            {user.isActive ? `Switch ${user.fullName.split(" ")[0]} off` : `Switch ${user.fullName.split(" ")[0]} on`}
          </Button>
        )}
        <LinkButton href="/admin/users" variant="quiet">
          {user ? "Back to users" : "Cancel"}
        </LinkButton>
      </div>
    </form>
  );
}

/** A new password, set by an admin. Every session they had ends. */
export function PasswordForm({ userId }: { userId: string }) {
  const [pending, start] = useTransition();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      noValidate
      className="flex flex-wrap items-end gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => {
          const result = await resetPassword(userId, password);
          if (result.ok) {
            setPassword("");
            setError(null);
            toast.success("Password set. Their sessions have ended.");
            return;
          }
          setError(result.fields?.password ?? result.error);
        });
      }}
    >
      <Field label="New password" error={error ?? undefined} className="min-w-60 flex-1">
        {(p) => <Input {...p} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />}
      </Field>
      <Button type="submit" loading={pending} disabled={!password}>
        Set password
      </Button>
    </form>
  );
}
