"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type {
  ComplianceRecord,
  CorporateDocument,
  ExecutiveNotification,
  ImmigrationRecord,
  OfficeTicket,
  PropertyRecord,
} from "@/src/platform/lib/types";

// --- Registrations & Permits (BOC, SEC, BIR, LGU, FDA) ---

export type PermitPayload = {
  title: string;
  category: string;
  agency: string;
  referenceNumber: string;
  issuanceDate?: string | null;
  expirationDate: string;
  renewalWindowDays?: number;
  status?: string;
  responsiblePerson?: string | null;
  estimatedCost?: number | null;
  notes?: string | null;
};

export async function savePermit(id: string | null, payload: PermitPayload): Promise<Result<ComplianceRecord>> {
  return attempt(async () => {
    const res = id
      ? await api.patch<ComplianceRecord>(`/admin/permits/${enc(id)}`, payload)
      : await api.post<ComplianceRecord>("/admin/permits", payload);
    refresh();
    return res;
  });
}

export async function deletePermit(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/admin/permits/${enc(id)}`);
    refresh();
    return null;
  });
}

// --- Expatriate & Immigration (ACR, AEP, Visas, Passports) ---

export type ImmigrationPayload = {
  individualName: string;
  designation: string;
  nationality: string;
  documentType: string;
  documentNumber: string;
  issuanceDate?: string | null;
  expirationDate: string;
  renewalLeadDays?: number;
  sponsoringEntity?: string | null;
  status?: string;
  assignedAssistant?: string | null;
  notes?: string | null;
};

export async function saveImmigration(id: string | null, payload: ImmigrationPayload): Promise<Result<ImmigrationRecord>> {
  return attempt(async () => {
    const res = id
      ? await api.patch<ImmigrationRecord>(`/admin/immigration/${enc(id)}`, payload)
      : await api.post<ImmigrationRecord>("/admin/immigration", payload);
    refresh();
    return res;
  });
}

export async function deleteImmigration(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/admin/immigration/${enc(id)}`);
    refresh();
    return null;
  });
}

// --- Corporate Documents & Contracts ---

export type DocumentPayload = {
  title: string;
  category: string;
  counterparty: string;
  referenceNumber?: string | null;
  effectiveDate?: string | null;
  expirationDate?: string | null;
  autoRenews?: boolean;
  noticePeriodDays?: number;
  custodian?: string | null;
  status?: string;
  annualValue?: number | null;
  notes?: string | null;
};

export async function saveDocument(id: string | null, payload: DocumentPayload): Promise<Result<CorporateDocument>> {
  return attempt(async () => {
    const res = id
      ? await api.patch<CorporateDocument>(`/admin/documents/${enc(id)}`, payload)
      : await api.post<CorporateDocument>("/admin/documents", payload);
    refresh();
    return res;
  });
}

export async function deleteDocument(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/admin/documents/${enc(id)}`);
    refresh();
    return null;
  });
}

// --- Real Estate & Properties (Offices, Warehouses, Utilities) ---

export type PropertyPayload = {
  name: string;
  propertyType: string;
  address: string;
  lessorName: string;
  lessorContact?: string | null;
  leaseStart?: string | null;
  leaseEnd: string;
  noticeDeadlineDays?: number;
  monthlyRent?: number | null;
  escalationRatePct?: number | null;
  securityDeposit?: number | null;
  utilitiesInfo?: string | null;
  status?: string;
  assignedManager?: string | null;
  notes?: string | null;
};

export async function saveProperty(id: string | null, payload: PropertyPayload): Promise<Result<PropertyRecord>> {
  return attempt(async () => {
    const res = id
      ? await api.patch<PropertyRecord>(`/admin/properties/${enc(id)}`, payload)
      : await api.post<PropertyRecord>("/admin/properties", payload);
    refresh();
    return res;
  });
}

export async function deleteProperty(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/admin/properties/${enc(id)}`);
    refresh();
    return null;
  });
}

// --- Office Concerns & Executive Service Desk (Tickets) ---

export type TicketPayload = {
  title: string;
  category: string;
  priority?: "urgent" | "high" | "normal" | "low";
  status?: "open" | "in_progress" | "pending_vendor" | "resolved" | "closed";
  requesterName: string;
  requesterEmail?: string | null;
  executiveSponsor?: string | null;
  assignedTo?: string | null;
  slaDueDate?: string | null;
  description: string;
  resolutionNotes?: string | null;
};

export async function saveTicket(id: string | null, payload: TicketPayload): Promise<Result<OfficeTicket>> {
  return attempt(async () => {
    const res = id
      ? await api.patch<OfficeTicket>(`/admin/tickets/${enc(id)}`, payload)
      : await api.post<OfficeTicket>("/admin/tickets", payload);
    refresh();
    return res;
  });
}

export async function addTicketUpdate(
  ticketId: string,
  payload: { authorName: string; content: string; newStatus?: string; updateType?: string },
): Promise<Result<OfficeTicket>> {
  return attempt(async () => {
    const res = await api.post<OfficeTicket>(`/admin/tickets/${enc(ticketId)}/updates`, payload);
    refresh();
    return res;
  });
}

export async function deleteTicket(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/admin/tickets/${enc(id)}`);
    refresh();
    return null;
  });
}

// --- Proactive Renewal Alerts & Notifications ---

export async function acknowledgeNotification(id: string): Promise<Result<ExecutiveNotification>> {
  return attempt(async () => {
    const res = await api.patch<ExecutiveNotification>(`/admin/notifications/${enc(id)}/acknowledge`, {});
    refresh();
    return res;
  });
}

export async function resolveNotification(id: string): Promise<Result<ExecutiveNotification>> {
  return attempt(async () => {
    const res = await api.patch<ExecutiveNotification>(`/admin/notifications/${enc(id)}/resolve`, {});
    refresh();
    return res;
  });
}

export async function syncNotificationsAction(): Promise<Result<{ ok: boolean; newOrUpdated: number }>> {
  return attempt(async () => {
    const res = await api.post<{ ok: boolean; newOrUpdated: number }>("/admin/notifications/sync", {});
    refresh();
    return res;
  });
}
