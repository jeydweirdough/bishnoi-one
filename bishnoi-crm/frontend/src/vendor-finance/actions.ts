"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Quote } from "@/src/platform/lib/types";

// The approver's decisions (quotes.approve). The API checks the permission, and that they reach the quote.

export type Decision = { decision: "approve" | "reject"; note: string | null };

/** Finance's word on a B2B quote's credit status (orders.credit): confirmed, on hold (with a reason), or checked again now. */
export async function decideCredit(id: string, input: { decision: "confirm" | "hold" | "recheck"; note: string | null }): Promise<Result> {
  return attempt(async () => {
    await api.post<Quote>(`/quotes/${enc(id)}/credit`, input);
    refresh();
    return null;
  });
}

export async function decideApproval(id: string, input: Decision): Promise<Result> {
  return attempt(async () => {
    await api.post<Quote>(`/quotes/${enc(id)}/approval`, input);
    refresh();
    return null;
  });
}

export async function checkLetter(id: string, input: Decision): Promise<Result> {
  return attempt(async () => {
    await api.post<Quote>(`/quotes/${enc(id)}/letter-check`, input);
    refresh();
    return null;
  });
}

export async function recordPayment(
  id: string,
  input: { paidOn: string; amountCentavos: number | null; reference: string | null },
): Promise<Result> {
  return attempt(async () => {
    await api.post<Quote>(`/quotes/${enc(id)}/payments`, input);
    refresh();
    return null;
  });
}
