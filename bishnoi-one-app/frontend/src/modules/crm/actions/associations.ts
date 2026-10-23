"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

// Associations (P13): records linked with a label. The API checks reach and
// the right to edit the record one links from.

export type AssocKind = "company" | "contact" | "deal";
export type AssocItem = { type: AssocKind; id: string; name: string; canOpen: boolean; associationId?: string; canRemove: boolean; fromField?: boolean };
export type AssocGroup = { label: string; side: "from" | "to"; name: string; items: AssocItem[] };
export type AssocLabel = { label: string; side: "from" | "to"; name: string; otherType: AssocKind };
export type Associations = { groups: AssocGroup[]; labels: AssocLabel[] };

export async function findTargets(kind: AssocKind, q: string): Promise<{ id: string; name: string; hint: string | null }[]> {
  return api.get<{ id: string; name: string; hint: string | null }[]>(`/associations/targets?type=${kind}&q=${enc(q.trim())}`).catch(() => []);
}

export async function addAssociation(input: { label: string; side: "from" | "to"; type: AssocKind; id: string; otherId: string }): Promise<Result<{ id: string }>> {
  return attempt(async () => {
    const r = await api.post<{ id: string }>("/associations", input);
    refresh();
    return r;
  });
}

export async function removeAssociation(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/associations/${enc(id)}`);
    refresh();
    return null;
  });
}
