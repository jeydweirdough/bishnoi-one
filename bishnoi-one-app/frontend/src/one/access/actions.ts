"use server";

import { revalidatePath } from "next/cache";
import { accountSend } from "@/src/platform/lib/account";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { AccessRole, ImportReport, RoleInput } from "./types";

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

export async function changePerson(id: string, change: { fullName?: string; title?: string | null; status?: "active" | "suspended" }): Promise<Result> {
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
