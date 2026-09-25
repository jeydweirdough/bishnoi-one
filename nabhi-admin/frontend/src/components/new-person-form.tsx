"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { AssignmentPicker, initialAssignment } from "../components/assignment-picker";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { createPerson, type AssignmentInput } from "../actions/admin";
import type { AppModule, OrgDivision, Role } from "@/src/platform/lib/types";

export function NewPersonForm({ roles, divisions, apps }: { roles: Role[]; divisions: OrgDivision[]; apps: AppModule[] }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [grant, setGrant] = useState(true);
  const [assignment, setAssignment] = useState<AssignmentInput>(() => initialAssignment(roles, divisions));
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const input = {
      fullName: name.trim(),
      email: String(data.get("email") ?? "").trim(),
      password: String(data.get("password") ?? ""),
      assignments: grant ? [assignment] : [],
    };
    start(async () => {
      const result = await createPerson(input);
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(`${input.fullName} added`, { description: "Give them their email and temporary password." });
      router.push(`/settings/people/${result.data.id}`);
    });
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-7">
      <fieldset className="grid gap-5 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold text-ink">Who</legend>
        <Field label="Full name" error={fields.fullName}>
          {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} autoFocus />}
        </Field>
        <Field label="Work email" error={fields.email}>
          {(p) => <Input {...p} name="email" type="email" inputMode="email" autoComplete="off" />}
        </Field>
        <Field
          label="Temporary password"
          error={fields.password}
          hint="At least 8 characters. Share it privately; they can't change it themselves yet, so an admin resets it."
          className="sm:col-span-2"
        >
          {(p) => <Input {...p} name="password" type="text" autoComplete="new-password" spellCheck={false} />}
        </Field>
      </fieldset>

      <fieldset className="space-y-4">
        <legend className="mb-3 text-sm font-semibold text-ink">What they can reach</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={grant} onChange={(e) => setGrant(e.target.checked)} className="size-4 accent-hema" />
          Give them a role now (you can add more after)
        </label>
        {grant && (
          <div className="animate-reshape">
            <AssignmentPicker
              roles={roles}
              divisions={divisions}
              apps={apps}
              personName={name.trim().split(" ")[0] || "They"}
              errors={fields}
              onChange={setAssignment}
            />
          </div>
        )}
      </fieldset>

      <FormError message={error} />
      <div className="flex gap-2 border-t border-rule pt-5">
        <Button type="submit" variant="primary" loading={pending}>
          Add person
        </Button>
        <LinkButton href="/settings/people" variant="quiet">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}
