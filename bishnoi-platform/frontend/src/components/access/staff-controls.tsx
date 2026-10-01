"use client";

import { toast } from "sonner";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { updateStaff } from "../../actions/users";
import type { Staff } from "../../lib/types";

/**
 * Beside a staff member: moving them between Platform Admin and Support, and
 * switching their account off or on. Nobody changes themselves (the API says
 * so too), so the platform can't be left with nobody to run it by one slip.
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
    <span className="flex flex-wrap gap-2">
      <ConfirmButton
        label={admin ? "Make Support" : "Make Platform Admin"}
        triggerSize="sm"
        triggerTitle={admin ? `Make ${person.fullName} Support` : `Make ${person.fullName} a Platform Admin`}
        danger={admin}
        title={admin ? `Make ${person.fullName} Support?` : `Make ${person.fullName} a Platform Admin?`}
        body={
          admin
            ? `${first} keeps seeing everything and working tickets and incidents, but can no longer change companies, users, applications, settings or staff.`
            : `${first} can change anything on the platform: companies, users and their access, applications, settings, and other staff.`
        }
        confirmLabel={admin ? "Make Support" : "Make Platform Admin"}
        onConfirm={() => change({ role: admin ? "member" : "admin" }, "Role changed")}
      />
      <ConfirmButton
        label={person.isActive ? "Switch off" : "Switch on"}
        triggerSize="sm"
        triggerTitle={person.isActive ? `Switch off ${person.fullName}'s account` : `Switch on ${person.fullName}'s account`}
        danger={person.isActive}
        title={person.isActive ? `Switch off ${person.fullName}'s account?` : `Switch ${person.fullName}'s account back on?`}
        body={
          person.isActive
            ? `${first} can't sign in to the console until it's switched back on${person.activeSessions ? ", and they're signed out wherever they are signed in" : ""}. Nothing they did is lost.`
            : `${first} can sign in to the console again, as ${person.roleName}.`
        }
        confirmLabel={person.isActive ? "Switch off" : "Switch on"}
        onConfirm={() => change({ isActive: !person.isActive }, person.isActive ? "Account switched off" : "Account switched on")}
      />
    </span>
  );
}
