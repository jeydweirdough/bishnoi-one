"use server";

import { api } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

// The command menu's search (benchmark G2): the API keeps each kind to what the person may see and reach.

export type SearchGroup = { kind: "customers" | "contacts" | "deals" | "quotes" | "products"; label: string; items: { id: string; title: string; sub: string | null; href: string }[] };

export async function searchAll(q: string): Promise<Result<SearchGroup[]>> {
  return attempt(async () => (await api.get<{ groups: SearchGroup[] }>(`/search?q=${encodeURIComponent(q)}`)).groups);
}
