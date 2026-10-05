"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { FundPurpose, FundRequest } from "../components/funds/types";

// Marketing requests: asking, the Team Lead's decision, and liquidating. The API
// checks every step (who may, and whether it's still possible) and, once
// Finance has the request, asks Finance.

export type FundInput = {
  purposeId: string;
  amountCentavos: number;
  neededOn: string | null;
  details: string;
  companyId: string | null;
};

export async function askForFunds(input: FundInput): Promise<Result<FundRequest>> {
  return attempt(async () => {
    const made = await api.post<FundRequest>("/funds", input);
    refresh();
    return made;
  });
}

export async function approveFunds(id: string, input: { approvedCentavos: number | null; liquidate: boolean; note: string | null }): Promise<Result<FundRequest>> {
  return attempt(async () => {
    const done = await api.post<FundRequest>(`/funds/${enc(id)}/approve`, input);
    refresh();
    return done;
  });
}

export async function declineFunds(id: string, note: string): Promise<Result<FundRequest>> {
  return attempt(async () => {
    const done = await api.post<FundRequest>(`/funds/${enc(id)}/decline`, { note });
    refresh();
    return done;
  });
}

export async function cancelFunds(id: string, reason: string | null): Promise<Result<FundRequest>> {
  return attempt(async () => {
    const done = await api.post<FundRequest>(`/funds/${enc(id)}/cancel`, { reason });
    refresh();
    return done;
  });
}

/** One receipt: the form's fields and its file (or why there's none). */
export async function addReceipt(id: string, form: FormData): Promise<Result<FundRequest>> {
  const body = new FormData();
  for (const key of ["spentOn", "description", "categoryId", "amountCentavos", "noReceiptReason"]) {
    const value = form.get(key);
    if (typeof value === "string" && value) body.set(key, value);
  }
  const file = form.get("receipt");
  if (file instanceof File && file.size > 0) body.set("receipt", file, file.name);
  return attempt(async () => {
    const done = await api.upload<FundRequest>(`/funds/${enc(id)}/expenses`, body);
    refresh();
    return done;
  });
}

export async function removeReceipt(id: string, expenseId: string): Promise<Result<FundRequest>> {
  return attempt(async () => {
    const done = await api.del<FundRequest>(`/funds/${enc(id)}/expenses/${enc(expenseId)}`);
    refresh();
    return done;
  });
}

export async function sendLiquidation(id: string): Promise<Result<FundRequest>> {
  return attempt(async () => {
    const done = await api.post<FundRequest>(`/funds/${enc(id)}/submit`, {});
    refresh();
    return done;
  });
}

export type PurposeInput = { name: string; description: string | null; liquidate: boolean; isActive: boolean };

export async function savePurpose(id: string | null, input: PurposeInput): Promise<Result<FundPurpose>> {
  return attempt(async () => {
    const saved = id ? await api.put<FundPurpose>(`/admin/fund-purposes/${enc(id)}`, input) : await api.post<FundPurpose>("/admin/fund-purposes", input);
    refresh();
    return saved;
  });
}
