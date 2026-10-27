"use server";

import { cookies } from "next/headers";
import { api, currentModule } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import { cookieOptions, viewAsCookie } from "@/src/platform/lib/session-cookie";

// Starting and stopping "view as" in the module the page is in (decided 2026-10-26). The module's
// API checks the administrator may, and keeps it in its activity log; the choice is kept in a
// cookie for that module only, sent with every request (src/platform/lib/api.ts).

export async function startViewAs(personId: string): Promise<Result<{ home: string }>> {
  return attempt(async () => {
    const mod = await currentModule();
    if (!mod || mod.accountOnly) throw new Error("Open a module first.");
    const who = await api.post<{ id: string; fullName: string; role: string }>("/auth/view-as", { userId: personId });
    (await cookies()).set(viewAsCookie(mod.key), [who.id, who.fullName, who.role].map((x) => x.replaceAll("|", " ")).join("|"), cookieOptions(8 * 3600));
    return { home: mod.path };
  });
}

export async function stopViewAs(): Promise<Result<{ home: string }>> {
  return attempt(async () => {
    const mod = await currentModule();
    if (mod) (await cookies()).delete(viewAsCookie(mod.key));
    return { home: mod?.path ?? "/" };
  });
}
