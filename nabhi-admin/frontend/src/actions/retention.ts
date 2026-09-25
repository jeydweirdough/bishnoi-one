"use server";

import { refresh } from "next/cache";
import { api } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { RetentionRules } from "@/src/platform/lib/types";

// Settings -> Retention. The API checks that the caller manages settings.

export async function saveRetentionRules(divisions: Record<string, RetentionRules>): Promise<Result> {
  return attempt(async () => {
    await api.put("/admin/retention", { divisions });
    refresh();
    return null;
  });
}
