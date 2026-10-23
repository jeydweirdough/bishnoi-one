"use server";

import { refresh } from "next/cache";
import { api } from "@/src/modules/admin/platform/lib/api";
import { attempt, type Result } from "@/src/modules/admin/platform/lib/result";

// Imports: a spreadsheet read by the API (never kept), its columns matched to
// our fields, checked row by row, then saved. The API checks the role on each
// call.

export type ImportKind = "permits" | "expatriates" | "documents" | "properties";

export type ImportFile = {
  fileName: string;
  headers: string[];
  rows: string[][];
  fields: { key: string; label: string; required: boolean; hint: string }[];
  /** field key -> column index; the API's guess from the headers. */
  mapping: Record<string, number | null>;
};

export type ImportResult = {
  added: number;
  updated: number;
  problems: { row: number; message: string }[];
  unmapped: string[];
};

export async function readImport(kind: ImportKind, form: FormData): Promise<Result<ImportFile>> {
  const body = new FormData();
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) return { ok: false, error: "Choose a file first." };
  body.set("file", file, file.name);
  return attempt(() => api.upload<ImportFile>(`/admin/imports/${kind}/read`, body));
}

export async function runImport(
  kind: ImportKind,
  input: { mapping: Record<string, number | null>; rows: string[][]; dryRun: boolean },
): Promise<Result<ImportResult>> {
  return attempt(async () => {
    const result = await api.post<ImportResult>(`/admin/imports/${kind}`, input);
    if (!input.dryRun) refresh();
    return result;
  });
}
