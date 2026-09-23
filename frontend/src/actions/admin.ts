"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { AdminUser, AppLink, Company, ListKind, ListSettings, OrgDivision, RolesPayload } from "@/src/platform/lib/types";

// The API checks that the caller manages settings on every one of these.

export type AssignmentInput = {
  roleKey: string;
  moduleKey: string;
  divisionCode: string | null;
  subdivisionCode: string | null;
};

/**
 * What an Admin may change about their own company; its slug and id are
 * not among them. Two screens share it: Company sends who the company is,
 * Money & formats sends how it writes things down.
 */
export type CompanyInput = {
  name?: string;
  brandName?: string;
  currency?: string;
  minorUnits?: number;
  locale?: string;
  timezone?: string;
  orderPrefix?: string;
};

export async function saveCompany(input: CompanyInput): Promise<Result<Company>> {
  return attempt(async () => {
    const saved = await api.patch<Company>("/admin/company", input);
    // The company's name, its money, its dates and its times are read from here
    // by every screen, so every one of them has to be told at once.
    refresh();
    return saved;
  });
}

export async function createPerson(input: {
  email: string;
  fullName: string;
  password: string;
  assignments: AssignmentInput[];
}): Promise<Result<{ id: string }>> {
  return attempt(async () => {
    const user = await api.post<AdminUser>("/admin/users", input);
    return { id: user.id };
  });
}

export async function updatePerson(
  id: string,
  input: { fullName?: string; isActive?: boolean; password?: string },
): Promise<Result> {
  return attempt(async () => {
    await api.patch<AdminUser>(`/admin/users/${enc(id)}`, input);
    refresh();
    return null;
  });
}

export async function addAssignment(userId: string, input: AssignmentInput): Promise<Result> {
  return attempt(async () => {
    await api.post<AdminUser>(`/admin/users/${enc(userId)}/assignments`, input);
    refresh();
    return null;
  });
}

export async function removeAssignment(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del<AdminUser>(`/admin/assignments/${enc(id)}`);
    refresh();
    return null;
  });
}

export async function savePermissions(permissions: RolesPayload["permissions"]): Promise<Result<RolesPayload>> {
  return attempt(async () => {
    const saved = await api.put<RolesPayload>("/admin/permissions", { permissions });
    refresh();
    return saved;
  });
}

export async function createRole(input: { name: string; description: string }): Promise<Result<RolesPayload>> {
  return attempt(async () => {
    const saved = await api.post<RolesPayload>("/admin/roles", input);
    refresh();
    return saved;
  });
}

export async function updateRole(key: string, input: { name?: string; description?: string }): Promise<Result<RolesPayload>> {
  return attempt(async () => {
    const saved = await api.patch<RolesPayload>(`/admin/roles/${enc(key)}`, input);
    refresh();
    return saved;
  });
}

export async function deleteRole(key: string): Promise<Result<RolesPayload>> {
  return attempt(async () => {
    const saved = await api.del<RolesPayload>(`/admin/roles/${enc(key)}`);
    refresh();
    return saved;
  });
}

export type ListItemInput = { code?: string; name: string; icon: string | null; isActive: boolean };

/**
 * One of the company's own pick-lists, replaced whole and in order. A choice
 * with no code is new; one left out is switched off rather than deleted, so the
 * records already carrying it keep their meaning.
 */
export async function saveRecordList(kind: ListKind, items: ListItemInput[]): Promise<Result> {
  return attempt(async () => {
    await api.put<ListSettings>(`/admin/lists/${enc(kind)}`, { items });
    refresh();
    return null;
  });
}

type Org = { divisions: OrgDivision[] };

/** A department of the company's own: it holds teams and people, and brings no screens. */
export async function addDepartment(name: string, icon: string | null): Promise<Result> {
  return attempt(async () => {
    await api.post<Org>("/admin/departments", { name, icon });
    refresh();
    return null;
  });
}

/**
 * A sales division of the company's own. It shares the sales workspace the six
 * built-in ones use and arrives with its pricing rules and retention window,
 * but with no price types: which prices it may quote is an admin's decision.
 */
export async function addDivision(name: string): Promise<Result> {
  return attempt(async () => {
    await api.post<Org>("/admin/departments", { name, kind: "sales" });
    refresh();
    return null;
  });
}

export async function updateDepartment(
  code: string,
  input: { name?: string; icon?: string; isActive?: boolean },
): Promise<Result> {
  return attempt(async () => {
    await api.patch<Org>(`/admin/departments/${enc(code)}`, input);
    refresh();
    return null;
  });
}

export async function addTeam(division: string, name: string): Promise<Result> {
  return attempt(async () => {
    await api.post<Org>(`/admin/teams/${enc(division)}`, { name });
    refresh();
    return null;
  });
}

export async function updateTeam(division: string, team: string, input: { name?: string; isActive?: boolean }): Promise<Result> {
  return attempt(async () => {
    await api.patch<Org>(`/admin/teams/${enc(division)}/${enc(team)}`, input);
    refresh();
    return null;
  });
}

export async function addHeadquarters(division: string, team: string, name: string): Promise<Result> {
  return attempt(async () => {
    await api.post<Org>(`/admin/teams/${enc(division)}/${enc(team)}/headquarters`, { name });
    refresh();
    return null;
  });
}

export async function updateHeadquarters(
  division: string,
  team: string,
  hq: string,
  input: { name?: string; isActive?: boolean },
): Promise<Result> {
  return attempt(async () => {
    await api.patch<Org>(`/admin/teams/${enc(division)}/${enc(team)}/headquarters/${enc(hq)}`, input);
    refresh();
    return null;
  });
}

export type AppLinkInput = {
  code: string | null;
  name: string;
  url: string;
  description: string;
  icon: string | null;
  isActive: boolean;
};

/** The whole list, as the screen holds it. A built-in app left out is kept
 *  rather than deleted — its permissions exist whether or not there is a link. */
export async function saveApps(apps: AppLinkInput[]): Promise<Result<{ apps: AppLink[] }>> {
  return attempt(async () => {
    const saved = await api.put<{ apps: AppLink[] }>("/admin/apps", { apps });
    refresh();
    return saved;
  });
}
