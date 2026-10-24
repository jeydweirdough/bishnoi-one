"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

// Promotional materials Admin asks to give to a team: the department's manager
// approves or rejects each (the API checks they run that team's department).

export type MaterialRequestStatus = "waiting" | "approved" | "rejected";

export type MaterialRequest = {
  id: string;
  reference: string;
  material: { no?: number | null; title?: string; kind?: string | null; product?: string | null };
  team: { id: string; name: string };
  recipient: { id: string; name: string } | null;
  quantity: number;
  purpose: string | null;
  requestedBy: string | null;
  status: MaterialRequestStatus;
  adminState: "requested" | "distributed" | "cancelled";
  distributedOn: string | null;
  note: string | null;
  decidedBy: string | null;
  decidedAt: string | null;
  receivedAt: string;
};

export async function decideMaterialRequest(id: string, outcome: "approved" | "rejected", note: string | null): Promise<Result<MaterialRequest>> {
  return attempt(async () => {
    const out = await api.post<MaterialRequest>(`/material-requests/${enc(id)}/decision`, { outcome, note });
    refresh();
    return out;
  });
}
