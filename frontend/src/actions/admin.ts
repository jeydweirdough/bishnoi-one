"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { AdminUserRow, RoleRow, Scope, TeamRow } from "@/src/platform/lib/types";

// Administration: Sales' own users, roles and teams. The API checks each
// permission and every rule (nobody left able to administer, a role in use
// can't go); these only carry the request and hand back what it said.

export type NewUser = { email: string; fullName: string; roleId: string; teamId: string | null; password: string };
export type UserChange = Partial<{ email: string; fullName: string; roleId: string; teamId: string | null; isActive: boolean }>;

export async function createUser(input: NewUser): Promise<Result<AdminUserRow>> {
  return attempt(async () => {
    const user = await api.post<AdminUserRow>("/admin/users", input);
    refresh();
    return user;
  });
}

export async function updateUser(id: string, change: UserChange): Promise<Result<AdminUserRow>> {
  return attempt(async () => {
    const user = await api.patch<AdminUserRow>(`/admin/users/${enc(id)}`, change);
    refresh();
    return user;
  });
}

export async function resetPassword(id: string, password: string): Promise<Result> {
  return attempt(async () => {
    await api.post(`/admin/users/${enc(id)}/password`, { password });
    return null;
  });
}

export type RoleInput = { name: string; description: string | null; scope: Scope; permissions: string[] };

export async function createRole(input: RoleInput): Promise<Result<RoleRow>> {
  return attempt(async () => {
    const role = await api.post<RoleRow>("/admin/roles", input);
    refresh();
    return role;
  });
}

export async function updateRole(id: string, change: Partial<RoleInput>): Promise<Result<RoleRow>> {
  return attempt(async () => {
    const role = await api.patch<RoleRow>(`/admin/roles/${enc(id)}`, change);
    refresh();
    return role;
  });
}

export async function deleteRole(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/admin/roles/${enc(id)}`);
    refresh();
    return null;
  });
}

export type TeamInput = { name: string; description: string | null };

export async function createTeam(input: TeamInput): Promise<Result<TeamRow>> {
  return attempt(async () => {
    const team = await api.post<TeamRow>("/admin/teams", input);
    refresh();
    return team;
  });
}

export async function updateTeam(id: string, change: Partial<TeamInput & { isActive: boolean }>): Promise<Result<TeamRow>> {
  return attempt(async () => {
    const team = await api.patch<TeamRow>(`/admin/teams/${enc(id)}`, change);
    refresh();
    return team;
  });
}

export async function deleteTeam(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/admin/teams/${enc(id)}`);
    refresh();
    return null;
  });
}
