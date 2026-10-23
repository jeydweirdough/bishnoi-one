"use server";

// Tickets and incidents: anyone signed in works them (app/routers/support.py, incidents.py).

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/console/platform/lib/api";
import { attempt, type Result } from "@/src/modules/console/platform/lib/result";
import type { Incident, IncidentKind, IncidentSeverity, IncidentStatus, Severity, Ticket, TicketKind, TicketStatus } from "@/src/modules/console/lib/types";

export type TicketInput = {
  kind: TicketKind;
  title: string;
  description?: string | null;
  severity: Severity;
  companyId?: string | null;
  applicationId?: string | null;
  identityId?: string | null;
  reporterName?: string | null;
  reporterEmail?: string | null;
  affectedUsers?: number | null;
  assigneeId?: string | null;
};

export async function addTicket(input: TicketInput): Promise<Result<Ticket>> {
  return attempt(async () => {
    const body = await api.post<{ ticket: Ticket }>("/platform/tickets", input);
    refresh();
    return body.ticket;
  });
}

export type TicketPatch = Partial<Omit<TicketInput, "identityId" | "reporterName" | "reporterEmail">> & {
  status?: TicketStatus;
  incidentId?: string | null;
  note?: string | null;
};

export async function updateTicket(id: string, patch: TicketPatch): Promise<Result> {
  return attempt(async () => {
    await api.patch(`/platform/tickets/${enc(id)}`, patch);
    refresh();
    return null;
  });
}

export async function addTicketNote(id: string, body: string): Promise<Result> {
  return attempt(async () => {
    await api.post(`/platform/tickets/${enc(id)}/notes`, { body });
    refresh();
    return null;
  });
}

export type IncidentInput = {
  title: string;
  kind: IncidentKind;
  severity: IncidentSeverity;
  applicationId?: string | null;
  companyIds: string[];
  summary?: string | null;
  leadId?: string | null;
  update?: string | null;
};

export async function declareIncident(input: IncidentInput): Promise<Result<Incident>> {
  return attempt(async () => {
    const body = await api.post<{ incident: Incident }>("/platform/incidents", input);
    refresh();
    return body.incident;
  });
}

export async function updateIncident(id: string, patch: Partial<Omit<IncidentInput, "update">>): Promise<Result> {
  return attempt(async () => {
    await api.patch(`/platform/incidents/${enc(id)}`, patch);
    refresh();
    return null;
  });
}

export async function postIncidentUpdate(id: string, status: IncidentStatus, body: string): Promise<Result> {
  return attempt(async () => {
    await api.post(`/platform/incidents/${enc(id)}/updates`, { status, body });
    refresh();
    return null;
  });
}
