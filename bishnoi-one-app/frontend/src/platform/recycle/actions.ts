"use server";

import { revalidatePath } from "next/cache";
import { apiFor } from "@/src/platform/lib/api";
import type { ModuleKey } from "@/src/platform/lib/modules";
import { attempt, type Result } from "@/src/platform/lib/result";

// Data clean-up and the recycle bin (2026-10-30): the same calls to every app's /data-cleanup (its
// app/recycle_bin.py). The app checks the person is an administrator on every call.

export type CleanupKind = { key: string; name: string; group: string; count: number; posted: boolean };
export type CleanupRecord = { id: string; label: string; sub: string | null; posted: boolean; createdAt: string | null };
export type BinItem = { id: string; kind: string; kindName: string; label: string; rows: number; deletedBy: string; deletedAt: string; expiresAt: string };

const enc = encodeURIComponent;

export async function cleanupRecords(module: ModuleKey, kind: string, q: string, page: number): Promise<Result<{ items: CleanupRecord[]; total: number; page: number; pageSize: number }>> {
  return attempt(() => apiFor(module).get(`/data-cleanup/kinds/${enc(kind)}?q=${enc(q)}&page=${page}`));
}

export async function deleteRecords(module: ModuleKey, kind: string, ids: string[], confirmPosted: boolean, path: string): Promise<Result<{ deleted: number }>> {
  return attempt(async () => {
    const r = await apiFor(module).post<{ deleted: number }>(`/data-cleanup/kinds/${enc(kind)}/delete`, { ids, confirmPosted });
    revalidatePath(path);
    return r;
  });
}

export async function restoreFromBin(module: ModuleKey, id: string, path: string): Promise<Result<{ restored: string }>> {
  return attempt(async () => {
    const r = await apiFor(module).post<{ restored: string }>(`/data-cleanup/bin/${enc(id)}/restore`, {});
    revalidatePath(path);
    return r;
  });
}

export async function eraseFromBin(module: ModuleKey, id: string | null, path: string): Promise<Result<{ erased: number }>> {
  return attempt(async () => {
    const r = await apiFor(module).del<{ erased: number }>(id ? `/data-cleanup/bin/${enc(id)}` : "/data-cleanup/bin");
    revalidatePath(path);
    return r;
  });
}
