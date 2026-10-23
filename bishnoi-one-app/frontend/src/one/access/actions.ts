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
