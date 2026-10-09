"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import { COMPANY_HEADER } from "@/src/platform/lib/session-cookie";
import type { Quote } from "@/src/platform/lib/types";

// Order links (the API's app/routers/quote_links.py) and quick quotes from the medicine search.

export type LinkState = "open" | "used" | "expired" | "switched_off";
export type QuoteLink = { id: string; state: LinkState; priceType: string; createdAt: string; expiresAt: string; usedAt: string | null; quoteId: string | null; customer: { id: string; name: string } | null; owner: { id: string; name: string } };
export type NewCustomer = { name: string; contactName: string | null; mobile: string | null; email: string | null; city: string | null };
export type QuoteLinks = { items: QuoteLink[]; priceTypes: { code: string; name: string }[]; lifetimes: number[] };
/** `askedPriceCentavos`: the price per unit the customer asks for instead (an order link's); the quote then waits for approval. */
export type OrderLine = { productId: string; quantity: number; askedPriceCentavos?: number };
export type Placed = { number: string; totalCentavos: number; lines: { name: string; quantity: number; totalCentavos: number }[]; waitsForApproval: boolean; rep: string };

/** A customer's links; with no customer, the links this person made (Customers → Order links). */
export async function quoteLinks(companyId: string | null): Promise<QuoteLinks> {
  return api.get<QuoteLinks>(companyId ? `/companies/${enc(companyId)}/quote-links` : "/quote-links");
}

/** A new link: its token comes back this once, to copy and send. */
/** With no customer: for someone not one yet, who becomes the rep's customer when they order. */
export async function makeQuoteLink(companyId: string | null, hours: number, priceType: string | null): Promise<Result<QuoteLink & { token: string }>> {
  return attempt(() => api.post<QuoteLink & { token: string }>(companyId ? `/companies/${enc(companyId)}/quote-links` : "/quote-links", { hours, priceType }));
}

/** A link's maker changes it while it hasn't been used: how long from now it works, its price, on or off. */
export async function changeQuoteLink(id: string, change: { hours?: number; priceType?: string; on?: boolean }): Promise<Result<QuoteLink>> {
  return attempt(() => api.patch<QuoteLink>(`/quote-links/${enc(id)}`, change));
}

/** Gone from the list, and it can't be opened; a quote it made stays. */
export async function deleteQuoteLink(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/quote-links/${enc(id)}`);
    return null;
  });
}

/** The customer's order, through the link: no account, the company named by the link's address. */
export async function placeOrder(company: string, token: string, lines: OrderLine[], note: string | null, customer: NewCustomer | null = null): Promise<Result<Placed>> {
  return attempt(() => api.post<Placed>(`/public/quote-links/${enc(token)}`, { lines, note, customer }, { [COMPANY_HEADER]: company }));
}

/** A rep's quote from the medicine search: the customer's list price, paid by the customer. */
export async function quickQuote(companyId: string, priceType: string, lines: OrderLine[]): Promise<Result<{ id: string; ready: boolean }>> {
  const body = new FormData();
  body.set("quote", JSON.stringify({ priceType, rx: false, payer: "self", notes: null, lines, letter: null }));
  return attempt(async () => {
    const quote = await api.upload<Quote>(`/companies/${enc(companyId)}/quotes`, body);
    refresh();
    return { id: quote.id, ready: quote.approval.status !== "pending" };
  });
}
