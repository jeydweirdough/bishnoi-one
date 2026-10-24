"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Activity, Customer, FollowUp, Quote, QuotePreview } from "@/src/platform/lib/types";

// Quotes. Every action goes through the API, which checks again that the
// person reaches the customer and may do this. Nothing here decides who may do what.

/** Who a quote is for: a company or a contact. */
export type QuoteFor = { kind: "companies" | "contacts"; id: string };

const forPath = (to: QuoteFor) => `/${to.kind === "contacts" ? "contacts" : "companies"}/${enc(to.id)}`;

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
  /** Added fields (Settings → Forms), by key. */
  extra?: Record<string, string | boolean | string[] | null>;
};

/** What the quote comes to, priced by the API with the customer's team's prices. Nothing is saved. */
export async function previewQuote(to: QuoteFor, input: QuoteInput): Promise<Result<QuotePreview>> {
  return attempt(() => api.post<QuotePreview>(`${forPath(to)}/quotes/preview`, { ...input, letter: null }));
}

/** `form` carries the quote as JSON in "quote" and, when DSWD, PCSO... pay, the letter in "letterFile". */
export async function createQuote(to: QuoteFor, form: FormData): Promise<Result<{ id: string }>> {
  const body = new FormData();
  body.set("quote", String(form.get("quote") ?? ""));
  const letter = form.get("letterFile");
  if (letter instanceof File && letter.size > 0) body.set("letterFile", letter, letter.name);
  return attempt(async () => {
    const quote = await api.upload<Quote>(`${forPath(to)}/quotes`, body);
    return { id: quote.id };
  });
}

export async function deleteQuote(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/quotes/${enc(id)}`);
    refresh();
    return null;
  });
}

// --- the older customer screens' actions. They go when those screens do (Retention's
// win-back is rebuilt on activities in the next step). ---

export type CustomerInput = Record<string, string | boolean | null>;

export async function createCustomer(input: CustomerInput): Promise<Result<{ id: string }>> {
  return attempt(async () => {
    const customer = await api.post<Customer>(`/crm/customers`, input);
    return { id: customer.id };
  });
}

export async function updateCustomer(id: string, input: CustomerInput): Promise<Result<{ id: string }>> {
  return attempt(async () => {
    await api.patch<Customer>(`/crm/customers/${enc(id)}`, input);
    return { id };
  });
}

export async function deleteCustomer(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/crm/customers/${enc(id)}`);
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
    await api.post<Activity>(`/crm/customers/${enc(customerId)}/activities`, input);
    refresh();
    return null;
  });
}

export async function deleteActivity(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/crm/activities/${enc(id)}`);
    refresh();
    return null;
  });
}

export async function addFollowUp(
  customerId: string,
  input: { title: string; dueOn: string; assigneeId: string | null },
): Promise<Result> {
  return attempt(async () => {
    await api.post<FollowUp>(`/crm/customers/${enc(customerId)}/follow-ups`, input);
    refresh();
    return null;
  });
}

export async function setFollowUpStatus(id: string, status: "open" | "done"): Promise<Result> {
  return attempt(async () => {
    await api.patch<FollowUp>(`/crm/follow-ups/${enc(id)}`, { status });
    refresh();
    return null;
  });
}
