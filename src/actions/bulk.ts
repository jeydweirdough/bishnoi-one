"use server";

// Inventory's bulk action. The API checks every product on its own and
// reports the ones it could not do; a big run is queued there.
import { refresh } from "next/cache";
import { api } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Job } from "@/src/platform/lib/types";

export type ProductsChange = { action: "activate" | "deactivate" } | { action: "reprice"; changeBp: number; priceType: string | null };

export async function bulkProducts(ids: string[], change: ProductsChange): Promise<Result<Job>> {
  return attempt(async () => {
    const job = await api.post<Job>("/inventory/bulk/products", { ...change, ids });
    if (job.status === "done") refresh();
    return job;
  });
}
