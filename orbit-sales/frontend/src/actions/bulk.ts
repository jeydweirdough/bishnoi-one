"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { CustomerList, CustomerStatus, Job } from "@/src/platform/lib/types";

// Bulk actions. The API checks every record on its own (visible, allowed in its
// team, still needing it) and reports the ones it couldn't do. Small jobs come
// back done; bigger ones are queued there, and the page follows their progress
// through /jobs/[id].

const MAX_BULK = 500;

async function submit(path: string, body: object): Promise<Result<Job>> {
  return attempt(async () => {
    const job = await api.post<Job>(path, body);
    if (job.status === "done") refresh();
    return job;
  });
}

export type CustomersChange =
  | { action: "status"; status: CustomerStatus }
  | { action: "owner"; ownerId: string }
  | { action: "follow_up"; followUp: { title: string; dueOn: string; assigneeId: string | null }; toOwner?: boolean }
  | { action: "delete" };

export async function bulkCustomers(ids: string[], change: CustomersChange): Promise<Result<Job>> {
  return submit("/sales/bulk/customers", { ...change, ids });
}

export type FollowUpsChange =
  | { action: "done" | "open" }
  | { action: "due"; dueOn: string }
  | { action: "assign"; assigneeId: string };

export async function bulkFollowUps(ids: string[], change: FollowUpsChange): Promise<Result<Job>> {
  return submit("/sales/bulk/follow-ups", { ...change, ids });
}


/** For "select all that match": every customer the filters find, up to what one bulk action takes. */
export async function customersMatching(filters: Record<string, string>): Promise<Result<{ id: string; name: string }[]>> {
  return attempt(async () => {
    const found: { id: string; name: string }[] = [];
    for (let offset = 0; offset < MAX_BULK; offset += 100) {
      const query = new URLSearchParams({ ...filters, limit: "100", offset: String(offset) });
      const page = await api.get<CustomerList>(`/sales/customers?${query}`);
      found.push(...page.items.map((c) => ({ id: c.id, name: c.name })));
      if (found.length >= page.total || page.items.length < 100) break;
    }
    return found.slice(0, MAX_BULK);
  });
}

/** Everyone who can be given these teams' customers or follow-ups. The teams
 *  may be in different divisions, so each says which. */
export async function divisionPeople(teams: { division: string; code: string }[]): Promise<Result<{ id: string; name: string }[]>> {
  return attempt(async () => {
    const lists = await Promise.all(
      teams.map((t) =>
        api.get<{ id: string; name: string }[]>(`/sales/people?division=${enc(t.division)}&team=${enc(t.code)}`),
      ),
    );
    const byId = new Map(lists.flat().map((p) => [p.id, p]));
    return [...byId.values()].sort((a, b) => a.name.localeCompare(b.name));
  });
}
