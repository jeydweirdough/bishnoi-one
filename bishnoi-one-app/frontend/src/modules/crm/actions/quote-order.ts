"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Quote } from "@/src/platform/lib/types";

/** Sends a ready quote to Bishnoi One Order. The API checks the role, that the quote
 *  is ready, and that it hasn't been ordered already. */
export async function raiseOrder(quoteId: string): Promise<Result<Quote>> {
  return attempt(async () => {
    const quote = await api.post<Quote>(`/quotes/${enc(quoteId)}/order`);
    refresh();
    return quote;
  });
}
