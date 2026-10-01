"use server";

// Platform users, their application access, access requests, staff and
// sessions (app/routers/users.py, access.py).

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { PlatformUser, Staff } from "../lib/types";

export type UserInput = {
  companyId: string;
  fullName: string;
  email: string;
  title?: string | null;
  isCompanyAdmin: boolean;
  applications: { applicationId: string; role?: string | null; isAppAdmin?: boolean }[];
};

export async function addUser(input: UserInput): Promise<Result<PlatformUser>> {
  return attempt(async () => {
    const body = await api.post<{ user: PlatformUser }>("/platform/users", input);
    refresh();
    return body.user;
  });
}

export type UserPatch = Partial<Omit<UserInput, "applications">> & { status?: PlatformUser["status"] };

export async function updateUser(id: string, patch: UserPatch): Promise<Result<{ withdrawnApplications: number }>> {
  return attempt(async () => {
    const body = await api.patch<{ withdrawnApplications: number }>(`/platform/users/${enc(id)}`, patch);
    refresh();
    return body;
  });
}

/** A first (or new) password for someone's Bishnoi One account, made here and shown once. Their sign-ins end. */
export async function makePassword(id: string): Promise<Result<string>> {
  return attempt(async () => {
    const body = await api.post<{ password: string }>(`/platform/users/${enc(id)}/password`, {});
    refresh();
    return body.password;
  });
}

/** Gives someone an application, or changes their role in it. */
export async function grantApplication(userId: string, appId: string, grant: { role?: string | null; isAppAdmin?: boolean }): Promise<Result> {
  return attempt(async () => {
    await api.put(`/platform/users/${enc(userId)}/applications/${enc(appId)}`, grant);
    refresh();
    return null;
  });
}

export async function withdrawApplication(userId: string, appId: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/platform/users/${enc(userId)}/applications/${enc(appId)}`);
    refresh();
    return null;
  });
}

export async function requestAccess(input: { identityId: string; applicationId: string; role?: string | null; reason?: string | null }): Promise<Result> {
  return attempt(async () => {
    await api.post("/platform/access/requests", input);
    refresh();
    return null;
  });
}

export async function decideRequest(id: string, approve: boolean, note?: string | null): Promise<Result> {
  return attempt(async () => {
    await api.post(`/platform/access/requests/${enc(id)}/decision`, { approve, note: note || null });
    refresh();
    return null;
  });
}

export async function updateStaff(id: string, patch: { role?: Staff["role"]; isActive?: boolean }): Promise<Result> {
  return attempt(async () => {
    await api.patch(`/platform/staff/${enc(id)}`, patch);
    refresh();
    return null;
  });
}

export async function endSession(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/platform/sessions/${enc(id)}`);
    refresh();
    return null;
  });
}
