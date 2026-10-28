"use server";

// Business events (app/routers/events.py, feature plan step 7): an operator's decisions on deliveries.

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/console/platform/lib/api";
import { attempt, type Result } from "@/src/modules/console/platform/lib/result";

export type Delivery = {
  eventId: string;
  kind: string;
  says: string;
  source: string;
  target: string;
  company: string | null;
  status: "pending" | "delivered" | "stuck" | "skipped";
  attempts: number;
  nextAt: string | null;
  lastError: string | null;
  deliveredAt: string | null;
  occurredAt: string;
};

export type EventsView = {
  counts: Record<"pending" | "delivered" | "stuck" | "skipped", number>;
  kinds: { kind: string; source: string; takers: string[]; says: string }[];
  deliveries: Delivery[];
};

export type CheckResult = { delivered: number; failed: number; pending: number; stuck: number; appsAsked: number };

export async function retryDelivery(eventId: string, target: string): Promise<Result<{ status: string }>> {
  return attempt(async () => {
    const r = await api.post<{ status: string }>(`/platform/events/${enc(eventId)}/${enc(target)}/retry`, {});
    refresh();
    return r;
  });
}

export async function skipDelivery(eventId: string, target: string): Promise<Result<{ status: string }>> {
  return attempt(async () => {
    const r = await api.post<{ status: string }>(`/platform/events/${enc(eventId)}/${enc(target)}/skip`, {});
    refresh();
    return r;
  });
}

export async function checkEvents(): Promise<Result<CheckResult>> {
  return attempt(async () => {
    const r = await api.post<CheckResult>("/platform/events/check", {});
    refresh();
    return r;
  });
}
