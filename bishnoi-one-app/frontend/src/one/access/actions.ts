"use server";

import { revalidatePath } from "next/cache";
import { accountSend } from "@/src/platform/lib/account";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { AccessRole, AppDetails, ImportReport, RoleInput } from "./types";

// A company administrator's changes to access, on Bishnoi One Platform
// (/identity/access). The Platform sends each module the change.

const enc = encodeURIComponent;
const refresh = () => revalidatePath("/platform", "layout");

export async function createRole(input: RoleInput): Promise<Result<AccessRole>> {
  return attempt(async () => {
    const role = await accountSend<AccessRole>("POST", "/identity/access/roles", input);
    refresh();
    return role;
  });
}

export async function updateRole(id: string, change: Partial<RoleInput>): Promise<Result<AccessRole>> {
  return attempt(async () => {
    const role = await accountSend<AccessRole>("PATCH", `/identity/access/roles/${enc(id)}`, change);
    refresh();
    return role;
  });
}

export async function deleteRole(id: string): Promise<Result> {
  return attempt(async () => {
    await accountSend("DELETE", `/identity/access/roles/${enc(id)}`);
    refresh();
    return null;
  });
}

export async function givePersonRole(personId: string, roleId: string | null): Promise<Result> {
  return attempt(async () => {
    await accountSend("PUT", `/identity/access/people/${enc(personId)}/role`, { roleId });
    refresh();
    return null;
  });
}

export async function setPersonModule(personId: string, key: string, on: boolean): Promise<Result> {
  return attempt(async () => {
    await accountSend(on ? "PUT" : "DELETE", `/identity/access/people/${enc(personId)}/apps/${enc(key)}`);
    refresh();
    return null;
  });
}

export async function importRoles(): Promise<Result<ImportReport>> {
  return attempt(async () => {
    const report = await accountSend<ImportReport>("POST", "/identity/access/import");
    refresh();
    return report;
  });
}

// People, kept here once for every module (R2, decided 2026-10-26).

export type PersonInput = { fullName: string; email: string; title: string | null; roleId: string | null; apps: string[] };

export async function addPerson(input: PersonInput): Promise<Result<{ person: { id: string; fullName: string }; hasPassword: boolean }>> {
  return attempt(async () => {
    const made = await accountSend<{ person: { id: string; fullName: string }; hasPassword: boolean }>("POST", "/identity/access/people", input);
    refresh();
    return made;
  });
}

export async function changePerson(id: string, change: { fullName?: string; title?: string | null; email?: string; status?: "active" | "suspended"; appDetails?: AppDetails }): Promise<Result> {
  return attempt(async () => {
    await accountSend("PATCH", `/identity/access/people/${enc(id)}`, change);
    refresh();
    return null;
  });
}

/** A made-up password (shown once), or the one typed. */
export async function setPersonPassword(id: string, password?: string): Promise<Result<{ password: string | null }>> {
  return attempt(async () => accountSend<{ password: string | null }>("POST", `/identity/access/people/${enc(id)}/password`, password ? { password } : {}));
}

// Abilities and job roles (feature plan step 6): roles in plain words; their permissions follow.

export async function roleFromJob(jobRole: string, name: string | null): Promise<Result<AccessRole>> {
  return attempt(async () => {
    const role = await accountSend<AccessRole>("POST", "/identity/access/roles/from-job", { jobRole, name });
    refresh();
    return role;
  });
}

export async function setRoleAbilities(id: string, abilities: { key: string; limit: number | null }[], scopes: Record<string, string>): Promise<Result<AccessRole>> {
  return attempt(async () => {
    const role = await accountSend<AccessRole>("PUT", `/identity/access/roles/${enc(id)}/abilities`, { abilities, scopes });
    refresh();
    return role;
  });
}

/** Deleted to the recycle bin: switched off, out of People, their sign-ins ended (2026-10-30). */
export async function deletePerson(id: string): Promise<Result> {
  return attempt(async () => {
    await accountSend("DELETE", `/identity/access/people/${enc(id)}`);
    refresh();
    return null;
  });
}

/** Back from the recycle bin onto People, still switched off until switched on. */
export async function restorePerson(id: string): Promise<Result> {
  return attempt(async () => {
    await accountSend("POST", `/identity/access/people/${enc(id)}/restore`, {});
    refresh();
    return null;
  });
}

/** An invitation (2026-10-30): a link for them to choose their own password, emailed when the company sends email; the link is given back to pass on. */
export async function invitePerson(id: string): Promise<Result<{ link: string; emailed: boolean }>> {
  return attempt(async () => accountSend<{ link: string; emailed: boolean }>("POST", `/identity/access/people/${enc(id)}/invite`, {}));
}

/** Their authenticator app lost: two-step sign-in off, to set up again at their next sign-in. */
export async function resetTwoStep(id: string): Promise<Result<{ reset: boolean }>> {
  return attempt(async () => accountSend<{ reset: boolean }>("POST", `/identity/access/people/${enc(id)}/two-step/reset`, {}));
}

export type ImportPeopleRow = { fullName: string; email: string; title?: string | null; role?: string | null; apps: string[] };
export type ImportPeopleResult = {
  rows: { n: number; fullName: string; email: string; title: string | null; role: string | null; apps: string[]; outcome: "new" | "already" | "problem"; reasons: string[] }[];
  counts: { new: number; already: number; problem: number };
  added?: number;
  invited?: number;
  emailed?: number;
};

/** People from a file: checked (apply false), or every new one added at once (apply true). */
export async function importPeople(rows: ImportPeopleRow[], apply: boolean, invite: boolean): Promise<Result<ImportPeopleResult>> {
  return attempt(async () => {
    const r = await accountSend<ImportPeopleResult>("POST", "/identity/access/people/import", { rows, apply, invite });
    if (apply) refresh();
    return r;
  });
}
