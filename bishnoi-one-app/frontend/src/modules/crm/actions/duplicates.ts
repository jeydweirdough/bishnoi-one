"use server";

import { refresh } from "next/cache";
import { api } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

// Possible duplicates: merge two into one, or say they're different. The API
// checks both are in reach and that the role may delete (the other one goes).

type Kind = "company" | "contact";

export async function mergeRecords(kind: Kind, keepId: string, mergeId: string): Promise<Result<{ keptId: string; filled: string[] }>> {
  return attempt(async () => {
    const merged = await api.post<{ keptId: string; filled: string[] }>("/duplicates/merge", { kind, keepId, mergeId });
    refresh();
    return merged;
  });
}

export async function markDifferent(kind: Kind, firstId: string, secondId: string): Promise<Result<null>> {
  return attempt(async () => {
    await api.post("/duplicates/different", { kind, firstId, secondId });
    refresh();
    return null;
  });
}
