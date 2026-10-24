"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/finance/platform/lib/api";
import { attempt, type Result } from "@/src/modules/finance/platform/lib/result";
import type { Reconciliation } from "@/src/modules/finance/bank/types";

export async function startReconciliation(input: { accountId: string; statementDate: string; statementBalanceCentavos: number }): Promise<Result<{ id: string }>> {
  return attempt(async () => {
    const made = await api.post<{ id: string }>("/finance/bank/reconciliations", input);
    refresh();
    return made;
  });
}

export async function saveCleared(id: string, lineIds: number[]): Promise<Result<Reconciliation>> {
  return attempt(async () => api.put<Reconciliation>(`/finance/bank/reconciliations/${enc(id)}/cleared`, { lineIds }));
}

export async function finishReconciliation(id: string): Promise<Result<Reconciliation>> {
  return attempt(async () => {
    const done = await api.post<Reconciliation>(`/finance/bank/reconciliations/${enc(id)}/finish`, {});
    refresh();
    return done;
  });
}

export async function discardReconciliation(id: string): Promise<Result<null>> {
  return attempt(async () => {
    await api.del(`/finance/bank/reconciliations/${enc(id)}`);
    refresh();
    return null;
  });
}
