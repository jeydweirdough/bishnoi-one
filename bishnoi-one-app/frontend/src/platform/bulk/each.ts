import "server-only";
import type { Job } from "../lib/types";

const MOST = 200;

/**
 * A bulk action made of the one-at-a-time action a list already has (2026-11-01): the API checks each record as it
 * always does, so a bulk delete can't do what a single one couldn't. One after another, so the log stays in order;
 * the answer is a finished job, with what couldn't be done by name for the bar's message.
 */
export async function eachOf(label: string, ids: string[], one: (id: string) => Promise<{ ok: true } | { ok: false; error: string }>): Promise<{ ok: true; data: Job } | { ok: false; error: string }> {
  if (ids.length > MOST) return { ok: false, error: `Choose ${MOST} or fewer at a time.` };
  const failures: Job["failures"] = [];
  for (const id of ids) {
    const r = await one(id).catch(() => ({ ok: false as const, error: "That didn't work." }));
    if (!r.ok) failures.push({ id, error: r.error });
  }
  return { ok: true, data: { id: "", label, status: "done", total: ids.length, processed: ids.length, succeeded: ids.length - failures.length, failed: failures.length, failures } };
}
