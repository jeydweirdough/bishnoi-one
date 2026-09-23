"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Activity, Customer, FollowUp, Quote, QuotePreview } from "@/src/platform/lib/types";

// Every action goes through the API, which checks the person's access to the
// record's (division, team) again. Nothing here decides who may do what.
//
// None of these name a division: the sales workspace spans every division a
// person sells in, and a record carries its own. The one exception is adding a
// customer, which has no record to read it off yet, so the form asks.

const base = "/sales";

export type CustomerInput = Record<string, string | boolean | null>;

export async function createCustomer(input: CustomerInput): Promise<Result<{ id: string }>> {
  return attempt(async () => {
    const customer = await api.post<Customer>(`${base}/customers`, input);
    return { id: customer.id };
  });
}

export async function updateCustomer(id: string, input: CustomerInput): Promise<Result<{ id: string }>> {
  return attempt(async () => {
    await api.patch<Customer>(`${base}/customers/${enc(id)}`, input);
    return { id };
  });
}

export async function deleteCustomer(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`${base}/customers/${enc(id)}`);
    return null;
  });
}

export type ActivityInput = {
  kind: string;
  outcome: string | null;
  summary: string;
  followUp: { title: string; dueOn: string; assigneeId: string | null } | null;
};

export async function logActivity(customerId: string, input: ActivityInput): Promise<Result> {
  return attempt(async () => {
    await api.post<Activity>(`${base}/customers/${enc(customerId)}/activities`, input);
    refresh();
    return null;
  });
}

export async function deleteActivity(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`${base}/activities/${enc(id)}`);
    refresh();
    return null;
  });
}

export async function addFollowUp(
  customerId: string,
  input: { title: string; dueOn: string; assigneeId: string | null },
): Promise<Result> {
  return attempt(async () => {
    await api.post<FollowUp>(`${base}/customers/${enc(customerId)}/follow-ups`, input);
    refresh();
    return null;
  });
}

export async function setFollowUpStatus(id: string, status: "open" | "done"): Promise<Result> {
  return attempt(async () => {
    await api.patch<FollowUp>(`${base}/follow-ups/${enc(id)}`, { status });
    refresh();
    return null;
  });
}

export type QuoteInput = {
  priceType: string;
  rx: boolean;
  payer: string;
  notes: string | null;
  // A line is either a product or a bundle. A bundle is priced whole, so it
  // carries nothing but which one and how many sets.
  lines: (
    | {
        productId: string;
        quantity: number;
        unitPriceCentavos: number | null;
        promoId: string | null;
        discount: { kind: "percent" | "amount"; value: number } | null;
      }
    | { bundleId: string; quantity: number }
  )[];
  letter: { number: string; issuedOn: string; amountCentavos: number | null } | null;
};

/** What the quote comes to, priced by the API with the division's rules. Nothing is saved. */
export async function previewQuote(customerId: string, input: QuoteInput): Promise<Result<QuotePreview>> {
  return attempt(() => api.post<QuotePreview>(`${base}/customers/${enc(customerId)}/quotes/preview`, { ...input, letter: null }));
}

/** `form` carries the quote as JSON in "quote" and, when DSWD, PCSO... pay, the letter in "letterFile". */
export async function createQuote(customerId: string, form: FormData): Promise<Result<{ id: string }>> {
  const body = new FormData();
  body.set("quote", String(form.get("quote") ?? ""));
  const letter = form.get("letterFile");
  if (letter instanceof File && letter.size > 0) body.set("letterFile", letter, letter.name);
  return attempt(async () => {
    const quote = await api.upload<Quote>(`${base}/customers/${enc(customerId)}/quotes`, body);
    return { id: quote.id };
  });
}

export async function deleteQuote(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`${base}/quotes/${enc(id)}`);
    return null;
  });
}
