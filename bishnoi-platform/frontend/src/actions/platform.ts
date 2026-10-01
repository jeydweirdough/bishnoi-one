"use server";

// Announcements, settings and your own password (app/routers/communications.py,
// settings.py, auth.py).

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { NoticeKind, NoticeLevel, PlatformSettings } from "../lib/types";

export type NoticeInput = {
  kind: NoticeKind;
  level: NoticeLevel;
  title: string;
  body?: string | null;
  companyId?: string | null;
  applicationId?: string | null;
  startsAt?: string | null;
  endsAt?: string | null;
  publish: boolean;
};

export async function addNotice(input: NoticeInput): Promise<Result> {
  return attempt(async () => {
    await api.post("/platform/announcements", input);
    refresh();
    return null;
  });
}

export async function updateNotice(id: string, patch: Partial<Omit<NoticeInput, "kind">>): Promise<Result> {
  return attempt(async () => {
    await api.patch(`/platform/announcements/${enc(id)}`, patch);
    refresh();
    return null;
  });
}

export async function deleteNotice(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/platform/announcements/${enc(id)}`);
    refresh();
    return null;
  });
}

export async function saveSettings<K extends keyof PlatformSettings>(section: K, value: PlatformSettings[K]): Promise<Result<PlatformSettings>> {
  return attempt(async () => {
    const body = await api.put<{ settings: PlatformSettings }>(`/platform/settings/${enc(section)}`, value);
    refresh();
    return body.settings;
  });
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<Result> {
  return attempt(async () => {
    await api.post("/auth/password", { currentPassword, newPassword });
    return null;
  });
}
