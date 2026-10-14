"use client";

import { Pencil, UserPlus } from "lucide-react";
import { useId, useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input, PasswordInput } from "@/src/platform/ui/field";
import { createStaff, updateStaff } from "../../actions/users";
import type { Staff } from "../../lib/types";
import { ICON_TRIGGER } from "../organizations/record-tools";

/** A password made here, shown once in a toast that stays until it's closed, to hand over. */
export function showPassword(name: string, password: string) {
  toast.success(`Password for ${name}: ${password}`, {
    description: "Shown only now. Give it to them in person or by another channel; they change it under Account.",
    duration: Infinity,
    action: { label: "Copy", onClick: () => navigator.clipboard?.writeText(password).catch(() => undefined) },
  });
}

const ROLES: { value: Staff["role"]; label: string }[] = [
  { value: "member", label: "Support" },
  { value: "admin", label: "Platform Admin" },
];

/**
 * Adding a staff member to this console, or changing one's name and email:
 * the same form in a dialog. A new account gets a password made here, shown
 * once (or one typed in); their role is changed with the buttons beside them.
 */
export function StaffForm({ person }: { person?: Staff }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const editing = Boolean(person);
  const [fullName, setFullName] = useState(person?.fullName ?? "");
  const [email, setEmail] = useState(person?.email ?? "");
  const [role, setRole] = useState<Staff["role"]>(person?.role ?? "member");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function show() {
    setFullName(person?.fullName ?? "");
    setEmail(person?.email ?? "");
    setRole(person?.role ?? "member");
    setPassword("");
    setError(null);
    dialog.current?.showModal();
  }

  function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    start(async () => {
      if (person) {
        const r = await updateStaff(person.id, { fullName, email });
        if (!r.ok) return setError(r.error);
        toast.success("Staff account changed", { description: fullName });
      } else {
        const r = await createStaff({ fullName, email, role, password: password || null });
        if (!r.ok) return setError(r.error);
        if (r.data) showPassword(fullName, r.data);
        else toast.success("Staff account added", { description: `${fullName} signs in with the password entered.` });
      }
      dialog.current?.close();
    });
  }

  return (
    <>
      {editing ? (
        <Button variant="quiet" size="sm" className={ICON_TRIGGER} title={`Edit ${person!.fullName}'s name or email`} onClick={show} aria-haspopup="dialog">
          <Pencil className="size-4" aria-hidden />
          <span className="sr-only">Edit {person!.fullName}&apos;s name or email</span>
        </Button>
      ) : (
        <Button variant="primary" icon={<UserPlus className="size-4" aria-hidden />} onClick={show} aria-haspopup="dialog">
          Add staff
        </Button>
      )}
      <dialog
        ref={dialog}
        onCancel={(e) => pending && e.preventDefault()}
        aria-labelledby={titleId}
        className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-[22px] bg-sheet p-0 text-ink shadow-overlay"
      >
        <form onSubmit={save} className="space-y-4 p-5">
          <h2 id={titleId} className="text-heading">
            {editing ? `Edit ${person!.fullName}` : "Add staff member"}
          </h2>
          {!editing && <p className="text-sm text-ink-2">Someone who signs in to this console. Platform Admins change anything; Support sees it all and works tickets and incidents.</p>}
          <Field label="Full name">{(p) => <Input {...p} value={fullName} onChange={(e) => setFullName(e.target.value)} required maxLength={120} autoFocus />}</Field>
          <Field label="Email">{(p) => <Input {...p} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required maxLength={254} />}</Field>
          {!editing && (
            <>
              <Choice name="role" legend="Role" value={role} options={ROLES} onChange={setRole} />
              <Field label="Password" optional hint="Leave blank to generate one, shown once. At least 8 characters.">
                {(p) => <PasswordInput {...p} value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} maxLength={256} autoComplete="new-password" />}
              </Field>
            </>
          )}
          <FormError message={error} />
          <div className="flex justify-end gap-2 pt-1">
            <Button onClick={() => !pending && dialog.current?.close()} disabled={pending}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={pending}>
              {editing ? "Save changes" : "Add staff"}
            </Button>
          </div>
        </form>
      </dialog>
    </>
  );
}
