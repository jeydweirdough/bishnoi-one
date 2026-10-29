"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/finance/platform/lib/api";
import { attempt, type Result } from "@/src/modules/finance/platform/lib/result";

// Banks, payments and equity (feature plan step 16). The API checks each person's role on every call.

type Json = Record<string, unknown>;

function sent<T>(run: () => Promise<T>): Promise<Result<T>> {
  return attempt(async () => {
    const out = await run();
    refresh();
    return out;
  });
}

export async function saveBankAccount(id: string | null, input: Json): Promise<Result<unknown>> {
  return sent(() => (id ? api.patch(`/finance/bank-accounts/${enc(id)}`, input) : api.post("/finance/bank-accounts", input)));
}
export async function saveRate(input: { currency: string; on: string; rate: number }): Promise<Result<unknown>> {
  return sent(() => api.put("/finance/exchange-rates", input));
}
export async function recordEquity(input: Json): Promise<Result<{ entryId: string; number: string }>> {
  return sent(() => api.post<{ entryId: string; number: string }>("/finance/equity/entries", input));
}
export async function closeYear(yearEnd: string, lock: boolean): Promise<Result<{ netIncomeCentavos: number; lockedUntil: string | null }>> {
  return sent(() => api.post<{ netIncomeCentavos: number; lockedUntil: string | null }>("/finance/closing", { yearEnd, lock }));
}
export async function setLock(lockedUntil: string | null): Promise<Result<{ lockedUntil: string | null }>> {
  return sent(() => api.put<{ lockedUntil: string | null }>("/finance/period-lock", { lockedUntil }));
}

// Fixed assets and budgets (step 17).
export async function addFixedAsset(input: Json): Promise<Result<unknown>> {
  return sent(() => api.post("/finance/fixed-assets", input));
}
export async function runDepreciation(through: string): Promise<Result<{ entries: { month: string; number: string; totalCentavos: number }[] }>> {
  return sent(() => api.post<{ entries: { month: string; number: string; totalCentavos: number }[] }>("/finance/fixed-assets/depreciate", { through }));
}
export async function disposeAsset(id: string): Promise<Result<unknown>> {
  return sent(() => api.post(`/finance/fixed-assets/${enc(id)}/dispose`, {}));
}
export async function saveBudget(input: Json): Promise<Result<unknown>> {
  return sent(() => api.put("/finance/budgets", input));
}
export async function deleteBudget(id: string): Promise<Result<null>> {
  return sent(() => api.del<null>(`/finance/budgets/${enc(id)}`));
}
