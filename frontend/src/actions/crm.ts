"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { ActivityItem, CompanyDetail, CompanyStatus, ContactDetail, CrmKind } from "@/src/platform/lib/types";

// Companies, contacts and activities. The API decides whose records someone
// reaches and what their role lets them do; these carry the request and hand
// back what it said.

export type CompanyInput = {
  name: string;
  status: CompanyStatus;
  industry: string | null;
  website: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  city: string | null;
  country: string | null;
  notes: string | null;
  ownerId: string | null;
};

export async function createCompany(input: CompanyInput): Promise<Result<CompanyDetail>> {
  return attempt(() => api.post<CompanyDetail>("/companies", input));
}

export async function updateCompany(id: string, change: Partial<CompanyInput>): Promise<Result<CompanyDetail>> {
  return attempt(async () => {
    const company = await api.patch<CompanyDetail>(`/companies/${enc(id)}`, change);
    refresh();
    return company;
  });
}

export async function deleteCompany(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/companies/${enc(id)}`);
    return null;
  });
}

export type ContactInput = {
  firstName: string;
  lastName: string | null;
  jobTitle: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  notes: string | null;
  companyId: string | null;
  ownerId: string | null;
};

export async function createContact(input: ContactInput): Promise<Result<ContactDetail>> {
  return attempt(() => api.post<ContactDetail>("/contacts", input));
}

export async function updateContact(id: string, change: Partial<ContactInput>): Promise<Result<ContactDetail>> {
  return attempt(async () => {
    const contact = await api.patch<ContactDetail>(`/contacts/${enc(id)}`, change);
    refresh();
    return contact;
  });
}

export async function deleteContact(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/contacts/${enc(id)}`);
    return null;
  });
}

export type ActivityInput = {
  kind: CrmKind;
  subject: string;
  body: string | null;
  /** Local time where the company is, as a datetime field gives it ("2026-09-24T14:00"). */
  at: string | null;
  companyId: string | null;
  contactId: string | null;
  durationMinutes: number | null;
  direction: "in" | "out" | null;
  ownerId: string | null;
  done?: boolean;
};

export async function createActivity(input: ActivityInput): Promise<Result<ActivityItem>> {
  return attempt(async () => {
    const activity = await api.post<ActivityItem>("/activities", input);
    refresh();
    return activity;
  });
}

export async function updateActivity(id: string, change: Partial<ActivityInput>): Promise<Result<ActivityItem>> {
  return attempt(async () => {
    const activity = await api.patch<ActivityItem>(`/activities/${enc(id)}`, change);
    refresh();
    return activity;
  });
}

export async function deleteActivity(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/activities/${enc(id)}`);
    refresh();
    return null;
  });
}
