"use server";

import { refresh } from "next/cache";
import { api, enc, load } from "@/src/modules/finance/platform/lib/api";
import { attempt, type Result } from "@/src/modules/finance/platform/lib/result";
import type { Bill, BillLine, BillSupplier, Delivery } from "@/src/modules/finance/bills/types";

// Supplier bills. The API works each one out (input VAT, the withholding),
// records it in the books, and checks the person's role for every step.

export type BillInput = {
  supplierId: string;
  supplierInvoiceNo: string;
  billDate: string;
  termsDays: number;
  deliveryRef: string | null;
  notes: string | null;
  amountsIncludeVat: boolean;
  lines: BillLine[];
  atc: string | null;
  ewtRateBp: number | null;
};

export async function findSuppliers(q: string): Promise<Result<BillSupplier[]>> {
  return attempt(async () => (await load<{ items: BillSupplier[] }>(`/finance/bills/suppliers?q=${enc(q)}`)).items);
}

export async function supplierDeliveries(id: string): Promise<Result<Delivery[]>> {
  return attempt(async () => (await load<{ items: Delivery[] }>(`/finance/bills/suppliers/${enc(id)}/deliveries`)).items);
}

export async function saveBill(id: string | null, input: BillInput): Promise<Result<Bill>> {
  return attempt(async () => {
    const saved = id ? await api.put<Bill>(`/finance/bills/${enc(id)}`, input) : await api.post<Bill>("/finance/bills", input);
    refresh();
    return saved;
  });
}

export async function deleteBill(id: string): Promise<Result<null>> {
  return attempt(async () => {
    await api.del(`/finance/bills/${enc(id)}`);
    refresh();
    return null;
  });
}

export async function recordBill(id: string): Promise<Result<Bill>> {
  return attempt(async () => {
    const done = await api.post<Bill>(`/finance/bills/${enc(id)}/record`, {});
    refresh();
    return done;
  });
}

export async function voidBill(id: string, reason: string): Promise<Result<Bill>> {
  return attempt(async () => {
    const done = await api.post<Bill>(`/finance/bills/${enc(id)}/void`, { reason });
    refresh();
    return done;
  });
}

export async function payBill(id: string, input: { paidOn: string; amountCentavos: number; method: string; reference: string | null }): Promise<Result<Bill>> {
  return attempt(async () => {
    const done = await api.post<Bill>(`/finance/bills/${enc(id)}/payments`, input);
    refresh();
    return done;
  });
}

export async function removeBillPayment(id: string, paymentId: string): Promise<Result<Bill>> {
  return attempt(async () => {
    const done = await api.del<Bill>(`/finance/bills/${enc(id)}/payments/${enc(paymentId)}`);
    refresh();
    return done;
  });
}
