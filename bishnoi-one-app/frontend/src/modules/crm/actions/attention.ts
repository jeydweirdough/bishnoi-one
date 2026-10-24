"use server";

import { api } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

/** One prompt on the home page (app/attention.py in the API). */
export type Prompt = { key: string; kind: string; title: string; reason: string; action: string; href: string; rank: number };

/** Puts a prompt aside: for a week ("snooze"), or for good ("dismiss"). */
export async function putAside(key: string, how: "snooze" | "dismiss"): Promise<Result> {
  return attempt(async () => {
    await api.post("/attention/put-aside", { key, how });
    return null;
  });
}
