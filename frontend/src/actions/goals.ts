"use server";

import { refresh } from "next/cache";
import { api } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

// Settings -> Goals. The API checks that the caller manages settings.

export async function saveGoalTargets(targets: Record<string, Record<string, number>>): Promise<Result> {
  return attempt(async () => {
    await api.put("/admin/goals", { targets });
    refresh();
    return null;
  });
}
