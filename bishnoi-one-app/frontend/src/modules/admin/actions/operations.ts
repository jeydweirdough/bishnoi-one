"use server";

// Fleet, travel and devices: adding, changing and deleting a record in one of
// the four lists (app/routers/operations.py). The API checks the permission.

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/admin/platform/lib/api";
import { attempt, type Result } from "@/src/modules/admin/platform/lib/result";

export type OperationsPath = "vehicles" | "fleet-cards" | "travel" | "devices";

export async function saveOperation(path: OperationsPath, id: string | null, payload: Record<string, unknown>): Promise<Result<Record<string, unknown>>> {
  return attempt(async () => {
    const res = id ? await api.patch<Record<string, unknown>>(`/admin/${path}/${enc(id)}`, payload) : await api.post<Record<string, unknown>>(`/admin/${path}`, payload);
    refresh();
    return res;
  });
}

export async function deleteOperation(path: OperationsPath, id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/admin/${path}/${enc(id)}`);
    refresh();
    return null;
  });
}

export type RecordPage = { record: Record<string, unknown> & { id: string }; history: { id: string; kind: string; text: string; by: string | null; at: string }[]; steps: string[] };

/** A quick step on one record (renewed, PMS done, booked, blocked, a note): the record and its history after it. */
export async function logStep(path: OperationsPath, id: string, action: string, note?: string): Promise<Result<RecordPage>> {
  return attempt(async () => {
    const res = await api.post<RecordPage>(`/admin/${path}/${enc(id)}/log`, { action, note: note ?? null });
    refresh();
    return res;
  });
}
