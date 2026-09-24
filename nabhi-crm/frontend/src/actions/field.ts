"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { FieldCounts, GoalsPayload, Pin, Visit, VisitOutcome } from "../components/field/types";
import type { Where } from "../components/field/where";

// Field work: logging visits, and the month's goals. The API checks who may.

export type VisitInput = {
  companyId: string;
  outcome: VisitOutcome;
  /** The company's local time ("2026-09-24T10:30"). */
  visitedAt: string | null;
  amountCentavos: number | null;
  receiptNo: string | null;
  notes: string | null;
  /** Where the phone was, if it said. */
  location: Where | null;
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

export async function pinClinic(companyId: string, where: Where): Promise<Result<{ pin: Pin }>> {
  return attempt(async () => {
    const pinned = await api.put<{ pin: Pin }>(`/field/doctors/${enc(companyId)}/location`, where);
    refresh();
    return pinned;
  });
}

export async function unpinClinic(companyId: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/field/doctors/${enc(companyId)}/location`);
    refresh();
    return null;
  });
}
