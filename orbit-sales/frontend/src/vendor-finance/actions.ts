"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Quote } from "@/src/platform/lib/types";

// Finance's decisions. The API checks the caller's Finance access to the quote's division and team.

export type Decision = { decision: "approve" | "reject"; note: string | null };

export async function decideApproval(id: string, input: Decision): Promise<Result> {
  return attempt(async () => {
    await api.post<Quote>(`/finance/quotes/${enc(id)}/approval`, input);
    refresh();
    return null;
  });
}

export async function checkLetter(id: string, input: Decision): Promise<Result> {
  return attempt(async () => {
    await api.post<Quote>(`/finance/quotes/${enc(id)}/letter-check`, input);
    refresh();
    return null;
  });
}

export async function recordPayment(
  id: string,
  input: { paidOn: string; amountCentavos: number | null; reference: string | null },
): Promise<Result> {
  return attempt(async () => {
    await api.post<Quote>(`/finance/quotes/${enc(id)}/payments`, input);
    refresh();
    return null;
  });
}
