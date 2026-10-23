"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Assistance, AssistanceProgram, AssistanceStatus, CareGroup, DoctorPlan, FieldCounts, GoalsPayload, Pin, PlanStop, Reaction, Visit, VisitBrief, VisitOutcome, Zone } from "@/src/modules/crm/components/field/types";
import type { Where } from "@/src/modules/crm/components/field/where";

// Field work: logging visits, and the month's goals. The API checks who may.

export type VisitInput = {
  companyId: string;
  outcome: VisitOutcome;
  /** The company's local time ("2026-09-24T10:30"). */
  visitedAt: string | null;
  amountCentavos: number | null;
  receiptNo: string | null;
  notes: string | null;
  /** The products detailed, in order (P6). */
  detailing: { productId: string; message: string | null; reaction: Reaction }[];
  nextObjective: string | null;
  /** The doctor's Patient Care Group, this visit. */
  careGroup?: CareGroup | null;
  /** Where the phone was, if it said. */
  location: Where | null;
};

/** The doctor's last objective and the products that can be detailed, for the visit form. */
export async function visitBrief(companyId: string): Promise<Result<VisitBrief>> {
  return attempt(() => api.get<VisitBrief>(`/field/visit-brief?company=${enc(companyId)}`));
}

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

/** A doctor's tier and zone: only what's given changes; null clears it. */
export async function setPlan(companyId: string, plan: { tier?: 1 | 2 | 3 | null; zone?: Zone | null }): Promise<Result<DoctorPlan>> {
  return attempt(async () => {
    const saved = await api.put<DoctorPlan>(`/field/doctors/${enc(companyId)}/plan`, plan);
    refresh();
    return saved;
  });
}

// The week's plan (app/routers/field_plan.py).

export async function addStop(companyId: string, day: string): Promise<Result<PlanStop>> {
  return attempt(async () => {
    const stop = await api.post<PlanStop>("/field/plan/stops", { companyId, day });
    refresh();
    return stop;
  });
}

export async function removeStop(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/field/plan/stops/${enc(id)}`);
    refresh();
    return null;
  });
}

export async function fillWeek(week: string): Promise<Result<{ added: number }>> {
  return attempt(async () => {
    const r = await api.post<{ added: number }>(`/field/plan/fill?week=${enc(week)}`, {});
    refresh();
    return r;
  });
}

export async function sendWeek(week: string): Promise<Result> {
  return attempt(async () => {
    await api.post(`/field/plan/send?week=${enc(week)}`, {});
    refresh();
    return null;
  });
}

export async function reviewWeek(person: string, week: string, note: string): Promise<Result> {
  return attempt(async () => {
    await api.post("/field/plan/review", { person, week, note: note || null });
    refresh();
    return null;
  });
}

// Government assistance applications (app/routers/assistance.py).

export type AssistanceInput = { program: AssistanceProgram; patientName: string; companyId: string; productIds: string[]; submittedOn: string; notes: string | null };

export async function fileAssistance(input: AssistanceInput): Promise<Result<Assistance>> {
  return attempt(async () => {
    const a = await api.post<Assistance>("/assistance", input);
    refresh();
    return a;
  });
}

export async function decideAssistance(id: string, change: { status: AssistanceStatus; receiptNo?: string; decidedOn?: string; submittedOn?: string; notes?: string }): Promise<Result<Assistance>> {
  return attempt(async () => {
    const a = await api.patch<Assistance>(`/assistance/${enc(id)}`, change);
    refresh();
    return a;
  });
}

export async function withdrawAssistance(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/assistance/${enc(id)}`);
    refresh();
    return null;
  });
}

/** Files on an application: the patient's IDs ("id") or other documents, several at once. */
export async function attachAssistance(id: string, kind: "id" | "document", form: FormData): Promise<Result<Assistance>> {
  return attempt(async () => {
    form.set("kind", kind);
    const a = await api.upload<Assistance>(`/assistance/${enc(id)}/files`, form);
    refresh();
    return a;
  });
}

export async function removeAssistanceFile(id: string, n: number): Promise<Result<Assistance>> {
  return attempt(async () => {
    const a = await api.del<Assistance>(`/assistance/${enc(id)}/files/${n}`);
    refresh();
    return a;
  });
}
