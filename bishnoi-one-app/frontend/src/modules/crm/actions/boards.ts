"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

// What a card moved on a list's board does (benchmark E1). The API checks the
// person may edit the record, and that the new value is one offered to them.

/** Customers by type: dropped in another column, the customer takes that type. */
export async function moveCustomerType(id: string, status: string): Promise<Result> {
  return attempt(async () => {
    await api.patch(`/companies/${enc(id)}`, { status });
    refresh();
    return null;
  });
}
