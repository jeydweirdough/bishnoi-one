"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/admin/platform/lib/api";
import { attempt, type Result } from "@/src/modules/admin/platform/lib/result";

type Json = Record<string, unknown>;

async function send<T = Json>(
  method: "post" | "put" | "patch" | "del",
  path: string,
  body?: unknown,
): Promise<Result<T>> {
  return attempt(async () => {
    const out = method === "del" ? await api.del<T>(path) : await api[method]<T>(path, body ?? {});
    refresh();
    return out;
  });
}

type Id = { id: string };

// --- users & accounts --------------------------------------------------------

export async function saveUser(id: string | null, input: Json): Promise<Result<unknown>> {
  return id ? send("patch", `/admin/users/${enc(id)}`, input) : send("post", "/admin/users", input);
}

export async function setUserPassword(id: string, password: string): Promise<Result<unknown>> {
  return attempt(async () => {
    await api.post(`/admin/users/${enc(id)}/password`, { password });
    return {};
  });
}

// --- roles & permissions -----------------------------------------------------

export async function saveRole(id: string | null, input: Json): Promise<Result<Id & { name: string }>> {
  return id ? send("patch", `/admin/roles/${enc(id)}`, input) : send("post", "/admin/roles", input);
}

export async function deleteRole(id: string): Promise<Result<null>> {
  return send<null>("del", `/admin/roles/${enc(id)}`);
}

// --- compatibility stubs for legacy screens ---
export type AssignmentInput = { roleKey: string; moduleKey: string; divisionCode: string | null; subdivisionCode: string | null };
export type CompanyInput = Record<string, unknown>;

export async function saveCompany(input: CompanyInput): Promise<Result<unknown>> { return send("patch", "/admin/company", input); }
export async function saveApps(apps: unknown): Promise<Result<unknown>> { return send("put", "/admin/apps", { apps }); }
export async function createPerson(input: unknown): Promise<Result<{ id: string }>> { return send("post", "/admin/users", input); }
export async function updatePerson(id: string, input: unknown): Promise<Result> { return send("patch", `/admin/users/${enc(id)}`, input); }
export async function addAssignment(userId: string, input: unknown): Promise<Result> { return send("post", `/admin/users/${enc(userId)}/assignments`, input); }
export async function removeAssignment(id: string): Promise<Result> { return send("del", `/admin/assignments/${enc(id)}`); }
export async function saveRecordList(kind: string, items: unknown): Promise<Result> { return send("put", `/admin/lists/${enc(kind)}`, { items }); }
export async function createRole(input: unknown): Promise<Result<unknown>> { return send("post", "/admin/roles", input); }
export async function updateRole(key: string, input: unknown): Promise<Result<unknown>> { return send("patch", `/admin/roles/${enc(key)}`, input); }
export async function savePermissions(permissions: unknown): Promise<Result<unknown>> { return send("put", "/admin/permissions", { permissions }); }
export async function addDepartment(name: string, icon: string): Promise<Result<unknown>> { return send("post", "/admin/departments", { name, icon }); }
export async function addDivision(name: string): Promise<Result<unknown>> { return send("post", "/admin/departments", { name, kind: "sales" }); }
export async function updateDepartment(code: string, input: unknown): Promise<Result<unknown>> { return send("patch", `/admin/departments/${enc(code)}`, input); }
export async function addTeam(division: string, name: string): Promise<Result<unknown>> { return send("post", `/admin/teams/${enc(division)}`, { name }); }
export async function updateTeam(division: string, team: string, input: unknown): Promise<Result<unknown>> { return send("patch", `/admin/teams/${enc(division)}/${enc(team)}`, input); }
export async function addHeadquarters(division: string, team: string, name: string): Promise<Result<unknown>> { return send("post", `/admin/teams/${enc(division)}/${enc(team)}/headquarters`, { name }); }
export async function updateHeadquarters(division: string, team: string, hq: string, input: unknown): Promise<Result<unknown>> { return send("patch", `/admin/teams/${enc(division)}/${enc(team)}/headquarters/${enc(hq)}`, input); }

