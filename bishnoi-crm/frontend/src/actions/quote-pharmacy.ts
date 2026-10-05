"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { PrescriptionDetails, Quote } from "@/src/platform/lib/types";

/** Sends an Rx quote, with its prescription's details, to Bishnoi One Pharmacy for
 *  the pharmacist's check. Sending again replaces the details. */
export async function sendToPharmacy(quoteId: string, input: PrescriptionDetails): Promise<Result<Quote>> {
  return attempt(async () => {
    const quote = await api.post<Quote>(`/quotes/${enc(quoteId)}/pharmacy-check`, input);
    refresh();
    return quote;
  });
}
