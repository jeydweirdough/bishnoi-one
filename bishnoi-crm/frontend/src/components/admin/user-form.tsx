"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { useAnticipation } from "@/src/platform/lib/anticipation";
import { createUser, updateUser, type UserChange } from "../../actions/admin";
import type { AdminUserRow, UserOptions } from "@/src/platform/lib/types";
import { SCOPE_WORDS } from "./words";
import { useCan } from "../quick-add/can";
import { AddTeam } from "../quick-add/forms";
import { QuickAdd } from "../quick-add/quick-add";

type Props = UserOptions & {
  user?: AdminUserRow; // editing when present
};

/** Adding a person, or changing one: name, email, role and team (and a first password when adding). */
export function UserForm({ roles, teams, user }: Props) {
  const router = useRouter();
  const [fullName, setFullName] = useState(user?.fullName ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [roleId, setRoleId] = useState(user?.role.id ?? roles.find((r) => r.name === "Salesperson")?.id ?? roles[0]?.id ?? "");
  const [teamId, setTeamId] = useState(user?.team?.id ?? "");
  const can = useCan();
  const [madeTeams, setMadeTeams] = useState<{ id: string; name: string }[]>([]);
  const [password, setPassword] = useState("");

  const { pending, shakeClass, anticipateClass, error, fieldErrors: fields, execute } = useAnticipation<{
    fullName: string;
    email: string;
    roleId: string;
    teamId: string;
  }>();

  // A switched-off team takes nobody new, but someone already in it stays listed.
  const pickableTeams = teams.filter((t) => t.isActive || t.id === user?.team?.id);
  const role = roles.find((r) => r.id === roleId);

  function submit() {
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

      execute({
        anticipate: () => ({
          fullName: user.fullName,
          email: user.email,
          roleId: user.role.id,
          teamId: user.team?.id ?? "",
        }),
        rollback: (previous) => {
          setFullName(previous.fullName);
          setEmail(previous.email);
          setRoleId(previous.roleId);
          setTeamId(previous.teamId);
        },
        request: () => updateUser(user.id, change),
        successMessage: (data) => ({
          title: "Changes saved",
          description: data.fullName,
        }),
        onSuccess: () => {
          router.refresh();
        },
      });
    } else {
      execute({
        anticipate: () => ({ fullName, email, roleId, teamId }),
        rollback: () => {},
        request: () =>
          createUser({
            fullName: fullName.trim(),
            email: email.trim(),
            roleId,
            teamId: teamId || null,
            password,
          }),
        successMessage: (data) => ({
          title: "Person added",
          description: data.fullName,
        }),
        onSuccess: () => {
          router.push("/admin/users");
          router.refresh();
        },
      });
    }
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className={`space-y-6 transition-all duration-300 ${shakeClass} ${anticipateClass}`}
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Full name" error={fields.fullName}>
          {(p) => <Input {...p} value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="off" required autoFocus={!user} />}
        </Field>
        <Field label="Work email" error={fields.email} hint={user ? undefined : "They sign in with this."}>
          {(p) => <Input {...p} type="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" required />}
        </Field>
        {/* Given, not typed: the next free number when they're added, and theirs alone. */}
        <Field label="Employee ID" hint={user ? "Given automatically, and theirs alone. Customers are transferred to a person by it." : "Given automatically when you add them: the next free number."}>
          {(p) => <Input {...p} value={user?.employeeId ?? "Given when added"} readOnly disabled={!user?.employeeId} aria-readonly className="font-mono" />}
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
        <div>
        <Field label="Team" optional error={fields.teamId}>
          {(p) => (
            <Select {...p} value={teamId} onChange={(e) => setTeamId(e.target.value)}>
              <option value="">No team</option>
              {madeTeams
                .filter((m) => !pickableTeams.some((t) => t.id === m.id))
                .map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              {pickableTeams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                  {t.isActive ? "" : " (inactive)"}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {can("admin.teams") && (
          <QuickAdd label="New team" title="New team">
            {(done) => <AddTeam onAdded={(t) => (setMadeTeams([t, ...madeTeams]), setTeamId(t.id))} done={done} />}
          </QuickAdd>
        )}
        </div>
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
