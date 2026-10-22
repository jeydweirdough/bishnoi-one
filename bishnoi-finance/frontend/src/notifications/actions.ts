"use server";

import { refresh } from "next/cache";
import { api } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Inbox } from "./types";

// The bell's two calls (app/routers/finance.py: /finance/notifications). The
// browser never calls the API itself.

export async function loadInbox(): Promise<Result<Inbox>> {
  return attempt(() => api.get<Inbox>("/finance/notifications"));
}

/** Marks these as read, or all of them when `ids` is left out. */
export async function markRead(ids?: string[]): Promise<Result<Inbox>> {
  return attempt(async () => {
    const inbox = await api.post<Inbox>("/finance/notifications/read", ids ? { ids } : {});
    refresh();
    return inbox;
  });
}
