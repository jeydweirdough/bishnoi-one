// What each recorded change was, said plainly. Anything not listed reads from its code.
export const AUDIT_ACTIONS: Record<string, string> = {
  "auth.signed_in": "Signed in",
  "auth.signed_out": "Signed out",
  "auth.sign_in_failed": "Failed to sign in",
  "user.created": "Added a person",
  "user.updated": "Changed a person",
  "user.switched_off": "Switched a person off",
  "user.switched_on": "Switched a person back on",
  "user.password_reset": "Set a new password",
  "role.created": "Added a role",
  "role.updated": "Changed a role",
  "role.deleted": "Deleted a role",
  "team.created": "Added a team",
  "team.updated": "Changed a team",
  "team.switched_off": "Switched a team off",
  "team.switched_on": "Switched a team back on",
  "team.deleted": "Deleted a team",
};

/** The filters the audit log offers: every action whose code starts with the key. */
export const AUDIT_FILTERS = [
  { key: "", label: "Everything" },
  { key: "auth.", label: "Sign-ins" },
  { key: "user.", label: "People" },
  { key: "role.", label: "Roles" },
  { key: "team.", label: "Teams" },
] as const;

/** Field names as the audit log stores them, said plainly. */
const FIELD_WORDS: Record<string, string> = {
  fullName: "name",
  email: "email",
  roleId: "role",
  teamId: "team",
  isActive: "on/off",
  name: "name",
  description: "description",
  scope: "whose records it reaches",
  permissions: "permissions",
};

export function describeAudit(action: string): string {
  return AUDIT_ACTIONS[action] ?? action.replaceAll(/[._]/g, " ");
}

export function describeFields(fields: string[]): string {
  return fields.map((f) => FIELD_WORDS[f] ?? f).join(", ");
}
