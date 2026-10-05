"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Deal, DealLists, DealStage, ForecastCategory, RevenueTargets } from "@/src/platform/lib/types";

// Deals: on a customer, through stages, won with a quote or lost with a reason.
// The API decides whose deals someone reaches and what their role lets them
// do; these carry the request and hand back what it said.

export type DealInput = {
  name: string;
  companyId: string;
  contactId: string | null;
  stageCode: string | null;
  probability?: number | null;
  forecastCategory?: Exclude<ForecastCategory, "closed"> | null;
  valueCentavos: number | null;
  expectedCloseOn: string;
  leadSource: string | null;
  priceType: string | null;
  lines: { productId: string; quantity: number }[];
  notes: string | null;
  ownerId: string | null;
};

export async function createDeal(input: DealInput): Promise<Result<Deal>> {
  return attempt(() => api.post<Deal>("/deals", input));
}

export async function updateDeal(id: string, change: Partial<Omit<DealInput, "companyId">>): Promise<Result<Deal>> {
  return attempt(async () => {
    const deal = await api.patch<Deal>(`/deals/${enc(id)}`, change);
    refresh();
    return deal;
  });
}

export async function winDeal(id: string, quoteId: string | null): Promise<Result<Deal>> {
  return attempt(async () => {
    const deal = await api.post<Deal>(`/deals/${enc(id)}/win`, { quoteId });
    refresh();
    return deal;
  });
}

export async function loseDeal(id: string, reason: string, competitor: string | null): Promise<Result<Deal>> {
  return attempt(async () => {
    const deal = await api.post<Deal>(`/deals/${enc(id)}/lose`, { reason, competitor });
    refresh();
    return deal;
  });
}

export async function reopenDeal(id: string, stageCode: string | null, expectedCloseOn: string): Promise<Result<Deal>> {
  return attempt(async () => {
    const deal = await api.post<Deal>(`/deals/${enc(id)}/reopen`, { stageCode, expectedCloseOn });
    refresh();
    return deal;
  });
}

export async function deleteDeal(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/deals/${enc(id)}`);
    return null;
  });
}

// --- an administrator's lists ---

export type DealStageChange = Partial<{
  name: string;
  probability: number;
  forecastCategory: Exclude<ForecastCategory, "closed">;
  sortOrder: number;
  isActive: boolean;
}>;

export async function saveDealStage(code: string | null, change: DealStageChange): Promise<Result<DealStage[]>> {
  return attempt(async () =>
    code ? await api.patch<DealStage[]>(`/admin/deal-stages/${enc(code)}`, change) : await api.post<DealStage[]>("/admin/deal-stages", change),
  );
}

export async function deleteDealStage(code: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/admin/deal-stages/${enc(code)}`);
    return null;
  });
}

export async function saveDealLists(lists: DealLists): Promise<Result<DealLists>> {
  return attempt(() => api.put<DealLists>("/admin/deal-lists", lists));
}

// --- revenue targets ---

export async function saveTargets(month: string, targets: { userId: string; amountCentavos: number | null }[]): Promise<Result<RevenueTargets>> {
  return attempt(async () => {
    const saved = await api.put<RevenueTargets>(`/sales/targets?month=${enc(month)}`, { targets });
    refresh();
    return saved;
  });
}
