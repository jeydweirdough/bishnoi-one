"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { createUser, updateUser, type UserChange } from "../../actions/admin";
import type { AdminUserRow, UserOptions } from "@/src/platform/lib/types";
import { SCOPE_WORDS } from "./words";

type Props = UserOptions & {
  user?: AdminUserRow; // editing when present
};

/** Adding a person, or changing one: name, email, role and team (and a first password when adding). */
export function UserForm({ roles, teams, user }: Props) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [fullName, setFullName] = useState(user?.fullName ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [roleId, setRoleId] = useState(user?.role.id ?? roles.find((r) => r.name === "Sales Rep")?.id ?? roles[0]?.id ?? "");
  const [teamId, setTeamId] = useState(user?.team?.id ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  // A switched-off team takes nobody new, but someone already in it stays listed.
  const pickableTeams = teams.filter((t) => t.isActive || t.id === user?.team?.id);
  const role = roles.find((r) => r.id === roleId);

  function submit() {
    start(async () => {
      let result;
      if (user) {
        const change: UserChange = {};
        if (fullName.trim() !== user.fullName) change.fullName = fullName.trim();
        if (email.trim().toLowerCase() !== user.email) change.email = email.trim();
        if (roleId !== user.role.id) change.roleId = roleId;
        if ((teamId || null) !== (user.team?.id ?? null)) change.teamId = teamId || null;
        if (Object.keys(change).length === 0) {
          toast("Nothing changed");
          return;
        }
        result = await updateUser(user.id, change);
      } else {
        result = await createUser({ fullName: fullName.trim(), email: email.trim(), roleId, teamId: teamId || null, password });
      }
      if (result.ok) {
        toast.success(user ? "Changes saved" : "Person added", { description: result.data.fullName });
        setError(null);
        setFields({});
        if (!user) router.push("/admin/users");
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
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Full name" error={fields.fullName}>
          {(p) => <Input {...p} value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="off" required autoFocus={!user} />}
        </Field>
        <Field label="Work email" error={fields.email} hint={user ? undefined : "They sign in with this."}>
          {(p) => <Input {...p} type="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" required />}
        </Field>
        <Field label="Role" error={fields.roleId} hint={role ? `${role.description ?? ""} ${SCOPE_WORDS[role.scope]}`.trim() : undefined}>
          {(p) => (
            <Select {...p} value={roleId} onChange={(e) => setRoleId(e.target.value)}>
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Team" optional error={fields.teamId}>
          {(p) => (
            <Select {...p} value={teamId} onChange={(e) => setTeamId(e.target.value)}>
              <option value="">No team</option>
              {pickableTeams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                  {t.isActive ? "" : " (switched off)"}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {!user && (
          <Field label="First password" error={fields.password} hint="At least 8 characters. Give it to them yourself; they can't reset it here.">
            {(p) => <Input {...p} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" required />}
          </Field>
        )}
      </div>
      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {user ? "Save changes" : "Add person"}
        </Button>
        <LinkButton href="/admin/users" variant="quiet">
          {user ? "Back to users" : "Cancel"}
        </LinkButton>
      </div>
    </form>
  );
}
