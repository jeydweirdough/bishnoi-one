"use client";

import { KeyRound, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { deleteStaff, resetStaffPassword, updateStaff } from "../../actions/users";
import type { Staff } from "../../lib/types";
import { ICON_TRIGGER, ICON_TRIGGER_DANGER } from "../organizations/record-tools";
import { showPassword, StaffForm } from "./staff-form";

/**
 * Beside a staff member: changing their name or email, moving them between
 * Platform Admin and Support, switching their account off or on, a new
 * password, and deleting it. Nobody does these to themselves, and the last
 * Platform Admin stays (the API says so too), so the platform can't be left
 * with nobody to run it by one slip.
 */
export function StaffControls({ person }: { person: Staff }) {
  const admin = person.role === "admin";
  const first = person.fullName.split(" ")[0];

  async function change(patch: { role?: Staff["role"]; isActive?: boolean }, done: string) {
    const result = await updateStaff(person.id, patch);
    if (!result.ok) {
      toast.error(result.error);
      return false;
    }
    toast.success(done, { description: person.fullName });
  }

  return (
    <span className="flex flex-wrap items-center gap-2">
      <StaffForm person={person} />
      <ConfirmButton
        label={<span className="sr-only">Reset {person.fullName}&apos;s password</span>}
        icon={<KeyRound className="size-4" aria-hidden />}
        triggerTitle={`Reset ${person.fullName}'s password`}
        triggerVariant="quiet"
        triggerSize="sm"
        triggerClassName={ICON_TRIGGER}
        danger={false}
        title={`Reset ${person.fullName}'s password?`}
        body={`A new password is generated and shown once. ${first} is signed out everywhere, signs in with it, then changes it under Account.`}
        confirmLabel="Reset password"
        onConfirm={async () => {
          const result = await resetStaffPassword(person.id);
          if (!result.ok) {
            toast.error(result.error);
            return false;
          }
          showPassword(person.fullName, result.data);
        }}
      />
      <ConfirmButton
        label={admin ? "Change role to Support" : "Change role to Platform Admin"}
        triggerSize="sm"
        triggerTitle={admin ? `Change ${person.fullName}'s role to Support` : `Change ${person.fullName}'s role to Platform Admin`}
        danger={admin}
        title={admin ? `Change ${person.fullName}'s role to Support?` : `Change ${person.fullName}'s role to Platform Admin?`}
        body={
          admin
            ? `${first} keeps seeing everything and working tickets and incidents, but can no longer change companies, users, applications, settings or staff.`
            : `${first} can change anything on the platform: companies, users and their access, applications, settings, and other staff.`
        }
        confirmLabel="Change role"
        onConfirm={() => change({ role: admin ? "member" : "admin" }, "Role changed")}
      />
      <ConfirmButton
        label={person.isActive ? "Deactivate" : "Activate"}
        triggerSize="sm"
        triggerTitle={person.isActive ? `Deactivate ${person.fullName}'s account` : `Activate ${person.fullName}'s account`}
        danger={person.isActive}
        title={person.isActive ? `Deactivate ${person.fullName}'s account?` : `Reactivate ${person.fullName}'s account?`}
        body={
          person.isActive
            ? `${first} can't sign in to the console until it's reactivated${person.activeSessions ? ", and they're signed out wherever they are signed in" : ""}. Nothing they did is lost.`
            : `${first} can sign in to the console again, as ${person.roleName}.`
        }
        confirmLabel={person.isActive ? "Deactivate" : "Activate"}
        onConfirm={() => change({ isActive: !person.isActive }, person.isActive ? "Account deactivated" : "Account activated")}
      />
      <ConfirmButton
        label={<span className="sr-only">Delete {person.fullName}&apos;s account</span>}
        icon={<Trash2 className="size-4" aria-hidden />}
        triggerTitle={`Delete ${person.fullName}'s account`}
        triggerVariant="quiet"
        triggerSize="sm"
        triggerClassName={ICON_TRIGGER_DANGER}
        title={`Delete ${person.fullName}'s account?`}
        body={`${first} can't sign in any more, and the account can't be restored. Their tickets and incidents stay, unassigned. To keep the account, deactivate it instead.`}
        confirmLabel="Delete account"
        onConfirm={async () => {
          const result = await deleteStaff(person.id);
          if (!result.ok) {
            toast.error(result.error);
            return false;
          }
          toast.success("Account deleted", { description: person.fullName });
        }}
      />
    </span>
  );
}
