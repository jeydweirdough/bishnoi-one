"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { KpiCatalogue, KpiDef, KpiTargets, KpiUnit } from "@/src/platform/lib/types";

// KPI management: defining KPIs (an administrator's), setting targets and
// entering results by hand (whoever sets goals). The API checks who may.

export type KpiInput = {
  name: string;
  description: string | null;
  measure: string;
  filters: Record<string, string>;
  unit: KpiUnit;
  better: "higher" | "lower";
  roles: string[];
  greenAt: number;
  amberAt: number;
  isActive: boolean;
};

export async function saveKpi(id: string | null, input: Partial<KpiInput>): Promise<Result<KpiDef>> {
  return attempt(async () => {
    const saved = id ? await api.patch<KpiDef>(`/admin/kpis/${enc(id)}`, input) : await api.post<KpiDef>("/admin/kpis", input);
    refresh();
    return saved;
  });
}

export async function deleteKpi(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/admin/kpis/${enc(id)}`);
    refresh();
    return null;
  });
}

export async function orderKpis(ids: string[]): Promise<Result<KpiCatalogue>> {
  return attempt(async () => {
    const saved = await api.put<KpiCatalogue>("/admin/kpis/order", { ids });
    refresh();
    return saved;
  });
}

export type TargetChange = { kpiId: string; userId?: string; teamId?: string; value: number | null };
export type EntryChange = { kpiId: string; userId: string; value: number | null };

export async function saveKpiTargets(month: string, targets: TargetChange[], entries: EntryChange[]): Promise<Result<KpiTargets>> {
  return attempt(async () => {
    let saved = await api.put<KpiTargets>(`/kpi-targets?month=${enc(month)}`, { targets });
    if (entries.length) saved = await api.put<KpiTargets>(`/kpi-entries?month=${enc(month)}`, { entries });
    refresh();
    return saved;
  });
}
