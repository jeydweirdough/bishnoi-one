"use server";

import { refresh } from "next/cache";
import { api } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Job } from "@/src/platform/lib/types";

// Deciding a pile of approvals at once. The API checks every quote on its own —
// visible, in a team this person works, still waiting — and reports the ones it
// could not do. A small run comes back done; a bigger one is queued there, and
// the page follows it through /jobs/[id].

export async function bulkApprovals(
  ids: string[],
  decision: { decision: "approve" | "reject"; note: string | null },
): Promise<Result<Job>> {
  return attempt(async () => {
    const job = await api.post<Job>("/finance/bulk/approvals", { ...decision, ids });
    if (job.status === "done") refresh();
    return job;
  });
}
