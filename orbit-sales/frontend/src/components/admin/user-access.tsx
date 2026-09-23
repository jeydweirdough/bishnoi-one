"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { resetPassword, updateUser } from "../../actions/admin";
import type { AdminUserRow } from "@/src/platform/lib/types";

/** Switching a person off (or back on), and giving them a new password. */
export function UserAccess({ user, isMe }: { user: AdminUserRow; isMe: boolean }) {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();

  async function toggle(): Promise<boolean> {
    const result = await updateUser(user.id, { isActive: !user.isActive });
    if (!result.ok) {
      toast.error(result.error);
      return false;
    }
    toast.success(user.isActive ? "Switched off" : "Switched back on", { description: user.fullName });
    router.refresh();
    return true;
  }

  function setNew() {
    start(async () => {
      const result = await resetPassword(user.id, password);
      if (!result.ok) {
        setError(result.fields?.password ?? result.error);
        return;
      }
      setPassword("");
      setError(null);
      toast.success("New password set", { description: `${user.fullName} is signed out everywhere and uses it from now on.` });
    });
  }

  return (
    <div className="space-y-6">
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          setNew();
        }}
        className="space-y-3"
      >
        <Field label="New password" hint="At least 8 characters. They're signed out everywhere and use it from their next sign-in.">
          {(p) => <Input {...p} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />}
        </Field>
        <FormError message={error} />
        <Button type="submit" size="sm" loading={saving} disabled={password.length === 0}>
          Set new password
        </Button>
      </form>

      <div className="border-t border-rule pt-5">
        {user.isActive ? (
          isMe ? (
            <p className="text-meta text-ink-3">You can't switch yourself off. Another administrator can.</p>
          ) : (
            <ConfirmButton
              label="Switch off"
              title={`Switch ${user.fullName} off?`}
              body="They're signed out at once and can't sign in again until someone switches them back on. Their history stays."
              confirmLabel="Switch off"
              triggerSize="sm"
              onConfirm={toggle}
            />
          )
        ) : (
          <ConfirmButton
            label="Switch back on"
            title={`Switch ${user.fullName} back on?`}
            body="They can sign in again with their last password."
            confirmLabel="Switch on"
            danger={false}
            triggerSize="sm"
            onConfirm={toggle}
          />
        )}
      </div>
    </div>
  );
}
