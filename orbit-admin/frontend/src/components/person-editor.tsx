"use client";

import { Trash2 } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { PhotoPicker } from "@/src/platform/account/photo-picker";
import { AssignmentPicker, initialAssignment } from "../components/assignment-picker";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { removePersonPhoto, savePersonPhoto } from "@/src/platform/actions/account";
import { addAssignment, removeAssignment, updatePerson, type AssignmentInput } from "../actions/admin";
import { accessLabel } from "@/src/platform/lib/labels";
import type { AdminUser, AppModule, OrgDivision, Role } from "@/src/platform/lib/types";

function useSubmit() {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  function run(
    work: () => Promise<{ ok: true } | { ok: false; error: string; fields?: Record<string, string> }>,
    success: string,
    after?: () => void,
  ) {
    start(async () => {
      const result = await work();
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      setError(null);
      setFields({});
      toast.success(success);
      after?.();
    });
  }
  return { pending, error, fields, run };
}

function Profile({ person }: { person: AdminUser }) {
  const [name, setName] = useState(person.fullName);
  const { pending, error, fields, run } = useSubmit();
  const first = person.fullName.split(" ")[0] || "their";
  return (
    <div className="space-y-5">
      <PhotoPicker
        name={person.fullName}
        id={person.id}
        photoAt={person.photoAt}
        whose={`${first}'s`}
        size="lg"
        onSave={(form) => savePersonPhoto(person.id, form)}
        onRemove={() => removePersonPhoto(person.id)}
      />
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          run(() => updatePerson(person.id, { fullName: name.trim() }), "Name saved");
        }}
        className="space-y-4"
      >
        <Field label="Full name" error={fields.fullName}>
          {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />}
        </Field>
        <Field label="Email" hint="Emails can't be changed yet.">
          {(p) => <Input {...p} value={person.email} disabled readOnly />}
        </Field>
        <FormError message={error} />
        <Button type="submit" size="sm" loading={pending} disabled={name.trim() === person.fullName}>
          Save name
        </Button>
      </form>
    </div>
  );
}

function Password({ person }: { person: AdminUser }) {
  const [value, setValue] = useState("");
  const { pending, error, fields, run } = useSubmit();
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        run(
          () => updatePerson(person.id, { password: value }),
          "Password reset",
          () => setValue(""),
        );
      }}
      className="space-y-4"
    >
      <Field
        label="New temporary password"
        error={fields.password}
        hint="At least 8 characters. Resetting signs them out everywhere; they sign in again with the new one."
      >
        {(p) => (
          <Input
            {...p}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            type="text"
            autoComplete="new-password"
            spellCheck={false}
          />
        )}
      </Field>
      <FormError message={error} />
      <Button type="submit" size="sm" loading={pending} disabled={!value}>
        Reset password
      </Button>
    </form>
  );
}

export function PersonEditor({
  person,
  roles,
  divisions,
  apps,
  isMe,
}: {
  person: AdminUser;
  roles: Role[];
  divisions: OrgDivision[];
  apps: AppModule[];
  isMe: boolean;
}) {
  const [assignment, setAssignment] = useState<AssignmentInput>(() => initialAssignment(roles, divisions));
  const [pickerKey, setPickerKey] = useState(0);
  const add = useSubmit();
  const first = person.fullName.split(" ")[0];

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
      <div className="space-y-5">
        <Sheet className="px-5 pt-4 pb-3">
          <SectionTitle icon="roles">Access</SectionTitle>
          {person.assignments.length === 0 ? (
            <p className="py-3 text-meta text-ink-3">{first} can&apos;t reach any module yet. Add a role below.</p>
          ) : (
            <ul className="divide-y divide-rule">
              {person.assignments.map((a) => (
                <li key={a.id} className="flex items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold">{a.roleName}</p>
                    <p className="text-meta text-ink-2">{accessLabel(a)}</p>
                  </div>
                  <ConfirmButton
                    label={
                      <span className="sr-only">
                        Remove {a.roleName} in {a.moduleName}
                      </span>
                    }
                    icon={<Trash2 className="size-4" aria-hidden />}
                    triggerVariant="quiet"
                    triggerSize="sm"
                    triggerClassName="!px-2 !text-ink-3 hover:!text-danger"
                    title={`Remove ${a.roleName} in ${a.moduleName}?`}
                    body={`${first} loses this access straight away, including anything already open on their screen.`}
                    confirmLabel="Remove"
                    onConfirm={async () => {
                      const result = await removeAssignment(a.id);
                      if (!result.ok) {
                        toast.error(result.error);
                        return false;
                      }
                      toast.success("Access removed");
                    }}
                  />
                </li>
              ))}
            </ul>
          )}
        </Sheet>

        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="addRole">Give another role</SectionTitle>
          <form
            noValidate
            className="mt-2 space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              add.run(
                () => addAssignment(person.id, assignment),
                "Access added",
                () => {
                  setPickerKey((k) => k + 1);
                  setAssignment(initialAssignment(roles, divisions));
                },
              );
            }}
          >
            <AssignmentPicker
              key={pickerKey}
              roles={roles}
              divisions={divisions}
              apps={apps}
              personName={first}
              errors={add.fields}
              onChange={setAssignment}
            />
            <FormError message={add.error} />
            <Button type="submit" variant="primary" loading={add.pending}>
              Add this access
            </Button>
          </form>
        </Sheet>
      </div>

      <div className="space-y-5">
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="profile">Profile</SectionTitle>
          <div className="mt-2">
            <Profile person={person} />
          </div>
        </Sheet>
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="password">Password</SectionTitle>
          <div className="mt-2">
            <Password person={person} />
          </div>
        </Sheet>
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="account">Account</SectionTitle>
          <p className="mt-1 mb-3 text-meta text-ink-2">
            {person.isActive
              ? "Switching the account off signs them out everywhere at once. Their records stay."
              : "This account is switched off. They can't sign in."}
          </p>
          {person.isActive ? (
            <ConfirmButton
              label="Switch off account"
              disabled={isMe}
              title={`Switch off ${person.fullName}?`}
              body="They're signed out straight away and can't sign in until someone switches the account back on."
              confirmLabel="Switch off"
              onConfirm={async () => {
                const result = await updatePerson(person.id, { isActive: false });
                if (!result.ok) {
                  toast.error(result.error);
                  return false;
                }
                toast.success("Account switched off");
              }}
            />
          ) : (
            <ConfirmButton
              label="Switch account back on"
              danger={false}
              title={`Switch ${person.fullName} back on?`}
              body="They can sign in again with their current password, and get the access listed on this page."
              confirmLabel="Switch on"
              onConfirm={async () => {
                const result = await updatePerson(person.id, { isActive: true });
                if (!result.ok) {
                  toast.error(result.error);
                  return false;
                }
                toast.success("Account switched on");
              }}
            />
          )}
          {isMe && <p className="mt-2 text-meta text-ink-3">You can&apos;t switch off your own account.</p>}
        </Sheet>
      </div>
    </div>
  );
}
