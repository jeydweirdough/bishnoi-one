"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/modules/pharmacy/platform/ui/button";
import { Field, FormError, FormGrid, Input } from "@/src/modules/pharmacy/platform/ui/field";
import { resetPassword, updateUser } from "@/src/modules/pharmacy/actions/pharmacy";
import type { AdminUser, RoleOption } from "@/src/modules/pharmacy/lib/types";

/**
 * What the Pharmacy keeps about a person: a pharmacist's licence number. Their name, email,
 * role, password and switching them off are kept once for every module in Bishnoi One's
 * People (R2, decided 2026-10-26), so here they're shown, not changed.
 */
export function UserForm({ user }: { roles?: RoleOption[]; user: AdminUser; isMe?: boolean }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [licenseNo, setLicenseNo] = useState(user.licenseNo ?? "");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  function submit() {
    start(async () => {
      const next = licenseNo.trim() || null;
      if (next === user.licenseNo) return void toast("Nothing changed");
      const r = await updateUser(user.id, { licenseNo: next });
      if (!r.ok) {
        setError(r.error);
        setFields(r.fields ?? {});
        return;
      }
      toast.success("Licence number saved", { description: user.fullName });
      setError(null);
      setFields({});
      router.refresh();
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
      <dl className="grid gap-4 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-meta text-ink-3">Full name</dt>
          <dd className="font-medium text-ink">{user.fullName}</dd>
        </div>
        <div>
          <dt className="text-meta text-ink-3">Work email</dt>
          <dd className="truncate text-ink">{user.email}</dd>
        </div>
        <div>
          <dt className="text-meta text-ink-3">Role</dt>
          <dd className="text-ink">{user.role.name}</dd>
        </div>
      </dl>
      <FormGrid>
        <Field label="Licence no." size="md" optional error={fields.licenseNo} hint="A pharmacist's PRC number, shown beside what they verify and dispense.">
          {(p) => <Input {...p} value={licenseNo} onChange={(e) => setLicenseNo(e.target.value)} autoFocus />}
        </Field>
      </FormGrid>
      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          Save
        </Button>
        <LinkButton href="/platform/roles/people" variant="quiet">
          Change name, role or password in People
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
