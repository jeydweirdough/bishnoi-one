"use server";

// Connections: the switchboard between applications (app/routers/connections.py).
// Platform Admins change them; the API checks on each call.

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

export async function makeConnectKey(appId: string): Promise<Result<{ key: string; replaced: boolean }>> {
  return attempt(async () => {
    const body = await api.post<{ key: string; replaced: boolean }>(`/platform/applications/${enc(appId)}/connect-key`, {});
    refresh();
    return body;
  });
}

export async function disconnectApp(appId: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/platform/applications/${enc(appId)}/connect-key`);
    refresh();
    return null;
  });
}

export async function addLink(fromAppId: string, toAppId: string): Promise<Result> {
  return attempt(async () => {
    await api.post("/platform/links", { fromAppId, toAppId });
    refresh();
    return null;
  });
}

export async function switchLink(id: string, isOn: boolean): Promise<Result> {
  return attempt(async () => {
    await api.patch(`/platform/links/${enc(id)}`, { isOn });
    refresh();
    return null;
  });
}

export async function newLinkKey(id: string): Promise<Result> {
  return attempt(async () => {
    await api.post(`/platform/links/${enc(id)}/new-key`, {});
    refresh();
    return null;
  });
}

export async function removeLink(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/platform/links/${enc(id)}`);
    refresh();
    return null;
  });
}
