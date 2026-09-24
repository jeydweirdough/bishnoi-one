"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { FieldCounts, GoalsPayload, Visit, VisitOutcome } from "../components/field/types";

// Field work: logging visits, and the month's goals. The API checks who may.

export type VisitInput = {
  companyId: string;
  outcome: VisitOutcome;
  /** The company's local time ("2026-09-24T10:30"). */
  visitedAt: string | null;
  amountCentavos: number | null;
  receiptNo: string | null;
  notes: string | null;
};

export async function logVisit(input: VisitInput): Promise<Result<Visit>> {
  return attempt(async () => {
    const visit = await api.post<Visit>("/visits", input);
    refresh();
    return visit;
  });
}

export async function deleteVisit(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/visits/${enc(id)}`);
    refresh();
    return null;
  });
}

export async function setGoals(month: string, goals: (FieldCounts & { userId: string })[]): Promise<Result<GoalsPayload>> {
  return attempt(async () => {
    const saved = await api.put<GoalsPayload>(`/field/goals?month=${enc(month)}`, { goals });
    refresh();
    return saved;
  });
}
