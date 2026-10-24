"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/finance/platform/lib/api";
import { attempt, type Result } from "@/src/modules/finance/platform/lib/result";
import type { Customer, Invoice, InvoiceLine, Series } from "@/src/modules/finance/invoices/types";

// Invoices. The API works each one out, numbers it from the series when it's
// issued, and checks the person's role for every step.

export type InvoiceInput = {
  customerId: string | null;
  customerName: string;
  customerTin: string | null;
  customerAddress: string | null;
  salespersonId: string | null;
  salespersonName: string | null;
  treatment: string;
  buyerIdNumber: string | null;
  invoiceDate: string;
  termsDays: number;
  reference: string | null;
  notes: string | null;
  pricesIncludeTax: boolean | null;
  lines: InvoiceLine[];
};

export async function saveInvoice(id: string | null, input: InvoiceInput): Promise<Result<Invoice>> {
  return attempt(async () => {
    const saved = id ? await api.put<Invoice>(`/finance/invoices/${enc(id)}`, input) : await api.post<Invoice>("/finance/invoices", input);
    refresh();
    return saved;
  });
}

export async function deleteInvoice(id: string): Promise<Result<null>> {
  return attempt(async () => {
    await api.del(`/finance/invoices/${enc(id)}`);
    refresh();
    return null;
  });
}

export async function issueInvoice(id: string, seriesId: string | null): Promise<Result<Invoice>> {
  return attempt(async () => {
    const issued = await api.post<Invoice>(`/finance/invoices/${enc(id)}/issue`, { seriesId });
    refresh();
    return issued;
  });
}

export async function voidInvoice(id: string, reason: string): Promise<Result<Invoice>> {
  return attempt(async () => {
    const voided = await api.post<Invoice>(`/finance/invoices/${enc(id)}/void`, { reason });
    refresh();
    return voided;
  });
}

/** Cancel and reissue: voids an issued invoice (reason needed) and answers a draft
 *  copying it, marked as its replacement. For a cancelled one: only the draft. */
export async function reissueInvoice(id: string, reason: string | null): Promise<Result<Invoice>> {
  return attempt(async () => {
    const copy = await api.post<Invoice>(`/finance/invoices/${enc(id)}/reissue`, { reason });
    refresh();
    return copy;
  });
}

export type PaymentInput = { paidOn: string; amountCentavos: number; method: string; reference: string | null };

export async function recordPayment(id: string, input: PaymentInput): Promise<Result<Invoice>> {
  return attempt(async () => {
    const saved = await api.post<Invoice>(`/finance/invoices/${enc(id)}/payments`, input);
    refresh();
    return saved;
  });
}

export async function removePayment(id: string, paymentId: string): Promise<Result<Invoice>> {
  return attempt(async () => {
    const saved = await api.del<Invoice>(`/finance/invoices/${enc(id)}/payments/${enc(paymentId)}`);
    refresh();
    return saved;
  });
}

/** The CRM's customers, for the invoice's "Bill to". */
export async function findCustomers(q: string): Promise<Result<Customer[]>> {
  return attempt(async () => (await api.get<{ items: Customer[] }>(`/finance/invoices/customers?q=${enc(q)}`)).items);
}

export type SeriesInput = { name: string; prefix: string; digits: number; firstNumber: number; lastNumber: number; atpNumber: string; atpDate: string };

export async function addSeries(input: SeriesInput): Promise<Result<Series>> {
  return attempt(async () => {
    const saved = await api.post<Series>("/finance/invoices/series", input);
    refresh();
    return saved;
  });
}

export async function switchSeries(id: string, isActive: boolean): Promise<Result<Series>> {
  return attempt(async () => {
    const saved = await api.patch<Series>(`/finance/invoices/series/${enc(id)}`, { isActive });
    refresh();
    return saved;
  });
}
