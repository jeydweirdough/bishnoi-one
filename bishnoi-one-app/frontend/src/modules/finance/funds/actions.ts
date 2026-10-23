"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/finance/platform/lib/api";
import { attempt, type Result } from "@/src/modules/finance/platform/lib/result";
import type { ExpenseCategory, FundRequest, Method } from "@/src/modules/finance/funds/types";

// Marketing requests: releasing, checking a liquidation, and settling it. The API
// checks each step is still possible (app/routers/funds.py).

const step = (id: string, path: string, body: unknown) =>
  attempt(async () => {
    const done = await api.post<FundRequest>(`/finance/funds/${enc(id)}/${path}`, body);
    refresh();
    return done;
  });

export async function releaseFunds(id: string, input: { amountCentavos: number; method: Method; reference: string | null; liquidateBy: string | null }): Promise<Result<FundRequest>> {
  return step(id, "release", input);
}

export async function refuseRelease(id: string, reason: string): Promise<Result<FundRequest>> {
  return step(id, "cancel", { reason });
}

export async function checkReceipt(id: string, expenseId: string, input: { accepted?: boolean | null; refusedReason?: string | null; categoryId?: string }): Promise<Result<FundRequest>> {
  return attempt(async () => {
    const done = await api.patch<FundRequest>(`/finance/funds/${enc(id)}/expenses/${enc(expenseId)}`, input);
    refresh();
    return done;
  });
}

export async function sendBack(id: string, note: string): Promise<Result<FundRequest>> {
  return step(id, "send-back", { note });
}

export async function finishCheck(id: string): Promise<Result<FundRequest>> {
  return step(id, "finish-check", {});
}

export async function recordMoney(id: string, kind: "returned" | "reimbursed", input: { amountCentavos: number; method: Method; reference: string | null }): Promise<Result<FundRequest>> {
  return step(id, kind, input);
}

export type CategoryInput = { name: string; parentId: string | null; accountId: string | null; reimbursable: boolean; description: string | null; isActive: boolean };

export async function saveCategory(id: string | null, input: CategoryInput): Promise<Result<ExpenseCategory>> {
  return attempt(async () => {
    const saved = id ? await api.put<ExpenseCategory>(`/finance/funds/categories/${enc(id)}`, input) : await api.post<ExpenseCategory>("/finance/funds/categories", input);
    refresh();
    return saved;
  });
}
