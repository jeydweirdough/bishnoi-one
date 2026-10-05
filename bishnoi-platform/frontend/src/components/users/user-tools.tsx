"use client";

import { Ban, KeyRound, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { makePassword, updateUser } from "../../actions/users";
import { ICON_TRIGGER, ICON_TRIGGER_DANGER } from "../organizations/record-tools";

/** Suspending a person, or bringing them back, from beside their name. Their access is kept either way. */
export function SuspendUser({ id, name, status }: { id: string; name: string; status: "active" | "suspended" }) {
  const suspended = status === "suspended";
  return (
    <ConfirmButton
      label={<span className="sr-only">{suspended ? `Reactivate ${name}` : `Suspend ${name}`}</span>}
      icon={suspended ? <RotateCcw className="size-4" aria-hidden /> : <Ban className="size-4" aria-hidden />}
      triggerTitle={suspended ? `Reactivate ${name}` : `Suspend ${name}`}
      triggerVariant="quiet"
      triggerSize="sm"
      triggerClassName={suspended ? ICON_TRIGGER : ICON_TRIGGER_DANGER}
      danger={!suspended}
      title={suspended ? `Reactivate ${name}?` : `Suspend ${name}?`}
      body={
        suspended
          ? `${name} can work again, with the applications and roles they had.`
          : `${name} can't work in any application while suspended. Their applications and roles are kept, and you can reactivate them any time.`
      }
      confirmLabel={suspended ? "Reactivate" : "Suspend user"}
      onConfirm={async () => {
        const result = await updateUser(id, { status: suspended ? "active" : "suspended" });
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success(suspended ? "User reactivated" : "User suspended", { description: name });
      }}
    />
  );
}

/** A first password for their Bishnoi One account (or a new one), shown once to hand over. */
export function MakePassword({ id, name, hasPassword }: { id: string; name: string; hasPassword: boolean }) {
  const label = hasPassword ? `Reset the password of ${name}` : `Make a first password for ${name}`;
  return (
    <ConfirmButton
      label={<span className="sr-only">{label}</span>}
      icon={<KeyRound className="size-4" aria-hidden />}
      triggerTitle={label}
      triggerVariant="quiet"
      triggerSize="sm"
      triggerClassName={ICON_TRIGGER}
      danger={false}
      title={hasPassword ? `Reset ${name}'s password?` : `Make a first password for ${name}?`}
      body={
        hasPassword
          ? `A new password is made and shown once. ${name} is signed out everywhere and signs in with it, then changes it.`
          : `A password is made and shown once. Give it to ${name}: they sign in with their Bishnoi One account, then change it.`
      }
      confirmLabel={hasPassword ? "Reset password" : "Make password"}
      onConfirm={async () => {
        const result = await makePassword(id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        const password = result.data;
        toast.success(`Password for ${name}: ${password}`, {
          description: "Shown only now. Give it to them in person or by another channel.",
          duration: Infinity,
          action: { label: "Copy", onClick: () => navigator.clipboard?.writeText(password).catch(() => undefined) },
        });
      }}
    />
  );
}
