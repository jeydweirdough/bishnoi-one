"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/finance/platform/lib/api";
import { attempt, type Result } from "@/src/modules/finance/platform/lib/result";
import type { AdvanceItem, CreditNoteItem, DocumentScanItem, RecurringItem, VendorCreditItem } from "./types";

export async function createCreditNote(input: Record<string, unknown>): Promise<Result<CreditNoteItem>> {
  return attempt(async () => {
    const r = await api.post<CreditNoteItem>("/finance/credit-notes", input);
    refresh();
    return r;
  });
}

export async function issueCreditNote(id: string): Promise<Result<CreditNoteItem>> {
  return attempt(async () => {
    const r = await api.post<CreditNoteItem>(`/finance/credit-notes/${enc(id)}/issue`, {});
    refresh();
    return r;
  });
}

export async function applyCreditNote(id: string, input: { invoiceId: string; appliedOn: string; amountCentavos: number }): Promise<Result<CreditNoteItem>> {
  return attempt(async () => {
    const r = await api.post<CreditNoteItem>(`/finance/credit-notes/${enc(id)}/apply`, input);
    refresh();
    return r;
  });
}

export async function removeCreditAllocation(id: string, allocId: string): Promise<Result<CreditNoteItem>> {
  return attempt(async () => {
    const r = await api.del<CreditNoteItem>(`/finance/credit-notes/${enc(id)}/allocations/${enc(allocId)}`);
    refresh();
    return r;
  });
}

export async function voidCreditNote(id: string, reason: string): Promise<Result<CreditNoteItem>> {
  return attempt(async () => {
    const r = await api.post<CreditNoteItem>(`/finance/credit-notes/${enc(id)}/void`, { reason });
    refresh();
    return r;
  });
}

export async function createVendorCredit(input: Record<string, unknown>): Promise<Result<VendorCreditItem>> {
  return attempt(async () => {
    const r = await api.post<VendorCreditItem>("/finance/vendor-credits", input);
    refresh();
    return r;
  });
}

export async function recordVendorCredit(id: string): Promise<Result<VendorCreditItem>> {
  return attempt(async () => {
    const r = await api.post<VendorCreditItem>(`/finance/vendor-credits/${enc(id)}/record`, {});
    refresh();
    return r;
  });
}

export async function applyVendorCredit(id: string, input: { billId: string; appliedOn: string; amountCentavos: number }): Promise<Result<VendorCreditItem>> {
  return attempt(async () => {
    const r = await api.post<VendorCreditItem>(`/finance/vendor-credits/${enc(id)}/apply`, input);
    refresh();
    return r;
  });
}

export async function removeVendorAllocation(id: string, allocId: string): Promise<Result<VendorCreditItem>> {
  return attempt(async () => {
    const r = await api.del<VendorCreditItem>(`/finance/vendor-credits/${enc(id)}/allocations/${enc(allocId)}`);
    refresh();
    return r;
  });
}

export async function voidVendorCredit(id: string, reason: string): Promise<Result<VendorCreditItem>> {
  return attempt(async () => {
    const r = await api.post<VendorCreditItem>(`/finance/vendor-credits/${enc(id)}/void`, { reason });
    refresh();
    return r;
  });
}

export async function createAdvance(input: Record<string, unknown>): Promise<Result<AdvanceItem>> {
  return attempt(async () => {
    const r = await api.post<AdvanceItem>("/finance/advances", input);
    refresh();
    return r;
  });
}

export async function applyAdvance(id: string, input: { targetId: string; appliedOn: string; amountCentavos: number }): Promise<Result<AdvanceItem>> {
  return attempt(async () => {
    const r = await api.post<AdvanceItem>(`/finance/advances/${enc(id)}/apply`, input);
    refresh();
    return r;
  });
}

export async function removeAdvanceApplication(id: string, appId: string): Promise<Result<AdvanceItem>> {
  return attempt(async () => {
    const r = await api.del<AdvanceItem>(`/finance/advances/${enc(id)}/applications/${enc(appId)}`);
    refresh();
    return r;
  });
}

export async function voidAdvance(id: string, reason: string): Promise<Result<AdvanceItem>> {
  return attempt(async () => {
    const r = await api.post<AdvanceItem>(`/finance/advances/${enc(id)}/void`, { reason });
    refresh();
    return r;
  });
}

export async function createRecurring(input: Record<string, unknown>): Promise<Result<RecurringItem>> {
  return attempt(async () => {
    const r = await api.post<RecurringItem>("/finance/recurring", input);
    refresh();
    return r;
  });
}

export async function toggleRecurring(id: string, isActive: boolean): Promise<Result<RecurringItem>> {
  return attempt(async () => {
    const r = await api.patch<RecurringItem>(`/finance/recurring/${enc(id)}`, { isActive });
    refresh();
    return r;
  });
}

export async function deleteRecurring(id: string): Promise<Result<null>> {
  return attempt(async () => {
    await api.del(`/finance/recurring/${enc(id)}`);
    refresh();
    return null;
  });
}

export async function runDueRecurring(): Promise<Result<{ generated: { kind: string; id: string; href: string; label: string }[]; count: number }>> {
  return attempt(async () => {
    const r = await api.post<{ generated: { kind: string; id: string; href: string; label: string }[]; count: number }>("/finance/recurring/run-due", {});
    refresh();
    return r;
  });
}

export async function generateRecurringNow(id: string): Promise<Result<{ kind: string; id: string; href: string; label: string }>> {
  return attempt(async () => {
    const r = await api.post<{ kind: string; id: string; href: string; label: string }>(`/finance/recurring/${enc(id)}/generate`, {});
    refresh();
    return r;
  });
}

export async function uploadDocumentScan(input: { name: string; contentType: string; data: string; ocrText?: string | null }): Promise<Result<DocumentScanItem>> {
  return attempt(async () => {
    const r = await api.post<DocumentScanItem>("/finance/scans", input);
    refresh();
    return r;
  });
}

export async function convertScanToBill(
  id: string,
  input: {
    supplierId: string;
    accountId: string;
    billNumber: string;
    billDate: string;
    amountCentavos: number;
    vat: string;
    description?: string;
    amountsIncludeVat: boolean;
  }
): Promise<Result<{ scanId: string; billId: string; billNo: number; href: string }>> {
  return attempt(async () => {
    const r = await api.post<{ scanId: string; billId: string; billNo: number; href: string }>(`/finance/scans/${enc(id)}/convert-to-bill`, input);
    refresh();
    return r;
  });
}

export async function deleteDocumentScan(id: string): Promise<Result<null>> {
  return attempt(async () => {
    await api.del(`/finance/scans/${enc(id)}`);
    refresh();
    return null;
  });
}
