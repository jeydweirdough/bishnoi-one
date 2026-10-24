"use server";

import { api } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import { crmPage, withCrmPages } from "@/src/modules/crm/lib/page";

// The command menu's search (benchmark G2): the API keeps each kind to what the person may see and reach.

export type SearchKind = "customers" | "contacts" | "deals" | "quotes" | "products";

/** One line of the preview: text, or an amount in centavos. */
export type SearchFact = { label: string; value?: string; amount?: number };

export type SearchItem = { id: string; title: string; sub: string | null; href: string; facts: SearchFact[]; actions: { label: string; href: string }[] };

/** One kind's matches: the first few, and how many there are in all. */
export type SearchGroup = { kind: SearchKind; label: string; total: number; items: SearchItem[] };

export async function searchAll(q: string, limit = 12): Promise<Result<SearchGroup[]>> {
  return attempt(async () =>
    (await api.get<{ groups: SearchGroup[] }>(`/search?q=${encodeURIComponent(q)}&limit=${limit}`)).groups.map((g) => ({
      ...g,
      // The API's page links, under /crm in the one app (lib/page.ts).
      items: g.items.map((i) => ({ ...i, href: crmPage(i.href), actions: withCrmPages(i.actions) })),
    })),
  );
}
