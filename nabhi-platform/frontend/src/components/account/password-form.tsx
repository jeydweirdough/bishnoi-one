"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { changePassword } from "../../actions/platform";

/** Your current password, then the new one twice. Every other sign-in of
 *  yours ends; this one carries on. */
export function PasswordForm() {
  const [pending, start] = useTransition();
  const [v, setV] = useState({ current: "", next: "", repeat: "" });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });

  function save() {
    const found: Record<string, string> = {};
    if (!v.current) found.currentPassword = "Type the password you use now.";
    if (v.next.length < 8) found.newPassword = "Use at least 8 characters.";
    else if (v.next === v.current) found.newPassword = "That's the one you have. Pick a new one.";
    if (!found.newPassword && v.repeat !== v.next) found.repeat = "This doesn't match the new password.";
    if (Object.keys(found).length) {
      setError(null);
      return setFields(found);
    }
    start(async () => {
      const r = await changePassword(v.current, v.next);
      if (!r.ok) {
        setError(r.fields && Object.keys(r.fields).length ? null : r.error);
        setFields(r.fields ?? {});
        return;
      }
      setError(null);
      setFields({});
      setV({ current: "", next: "", repeat: "" });
      toast.success("Password changed", { description: "Your other sign-ins have ended. This one carries on." });
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
      className="mt-2 grid gap-5"
    >
      <p className="text-meta text-ink-3">Changing it ends your other sign-ins, on any other computer or browser. This one carries on.</p>
      <Field label="Current password" error={fields.currentPassword}>
        {(p) => <Input {...p} type="password" autoComplete="current-password" value={v.current} onChange={set("current")} />}
      </Field>
      <Field label="New password" error={fields.newPassword} hint="At least 8 characters.">
        {(p) => <Input {...p} type="password" autoComplete="new-password" value={v.next} onChange={set("next")} />}
      </Field>
      <Field label="New password again" error={fields.repeat}>
        {(p) => <Input {...p} type="password" autoComplete="new-password" value={v.repeat} onChange={set("repeat")} />}
      </Field>
      <div>
        <FormError message={error} />
        <Button type="submit" variant="primary" loading={pending} className="mt-2">
          Change your password
        </Button>
      </div>
    </form>
  );
}
