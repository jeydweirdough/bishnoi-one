"use server";

// Finding the platform user who reported a ticket, as someone types.

import { api } from "@/src/modules/console/platform/lib/api";
import { attempt, type Result } from "@/src/modules/console/platform/lib/result";
import type { PlatformUser } from "@/src/modules/console/lib/types";

export type Found = { id: string; name: string; email: string; companyId: string; companyName: string | null };

export async function findUsers(q: string): Promise<Result<Found[]>> {
  return attempt(async () => {
    if (q.trim().length < 2) return [];
    const body = await api.get<{ users: PlatformUser[] }>(`/platform/users?q=${encodeURIComponent(q.trim())}`);
    return body.users.slice(0, 8).map((u) => ({ id: u.id, name: u.fullName, email: u.email, companyId: u.companyId, companyName: u.companyName }));
  });
}
