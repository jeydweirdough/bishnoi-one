"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { ActivityItem, CompanyDetail, CompanyRow, CompanyStatus, ContactDetail, CrmKind, Job, Paged } from "@/src/platform/lib/types";

// Companies, contacts and activities. The API decides whose records someone
// reaches and what their role lets them do; these carry the request and hand
// back what it said.

export type CompanyInput = {
  name: string;
  allowDuplicate?: boolean;
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
  /** Added fields (Settings → Forms), by key: only what changed (null clears one). */
  extra?: Record<string, string | boolean | string[] | null>;
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
  allowDuplicate?: boolean;
  lastName: string | null;
  jobTitle: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  notes: string | null;
  companyId: string | null;
  ownerId: string | null;
  /** Added fields (Settings → Forms), by key: only what changed (null clears one). */
  extra?: Record<string, string | boolean | string[] | null>;
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

// --- bulk -------------------------------------------------------------------------------

export type RecordsChange =
  | { action: "status"; status: CompanyStatus }
  | { action: "owner"; ownerId: string }
  | { action: "follow_up"; followUp: { title: string; dueOn: string }; toOwner: boolean }
  | { action: "delete" };

/** Many companies or contacts at once. The API checks each one and says which it couldn't do. */
export async function bulkRecords(kind: "companies" | "contacts", ids: string[], change: RecordsChange): Promise<Result<Job>> {
  return attempt(async () => {
    const job = await api.post<Job>(`/${kind}/bulk`, { ...change, ids });
    refresh();
    return job;
  });
}

export type ActivitiesChange = { action: "done" | "open" } | { action: "due"; dueOn: string } | { action: "assign"; assigneeId: string };

export async function bulkActivities(ids: string[], change: ActivitiesChange): Promise<Result<Job>> {
  return attempt(async () => {
    const job = await api.post<Job>("/activities/bulk", { ...change, ids });
    refresh();
    return job;
  });
}

/** For "select all that match": every company or contact the filters find, up to what one bulk action takes. */
export async function recordsMatching(kind: "companies" | "contacts", filters: Record<string, string>): Promise<Result<{ id: string; name: string }[]>> {
  return attempt(async () => {
    const found: { id: string; name: string }[] = [];
    for (let offset = 0; offset < 500; offset += 200) {
      const page = await api.get<{ items: { id: string; name: string }[]; total: number }>(`/${kind}?${new URLSearchParams({ ...filters, limit: "200", offset: String(offset) })}`);
      found.push(...page.items.map((r) => ({ id: r.id, name: r.name })));
      if (found.length >= page.total) break;
    }
    return found.slice(0, 500);
  });
}

/** Customers whose name has these words: for pickers, past the first page. */
export async function findCustomers(words: string): Promise<Result<{ id: string; name: string }[]>> {
  return attempt(async () => {
    const found = await api.get<Paged<CompanyRow>>(`/companies?q=${enc(words)}&limit=30`);
    return found.items.map((c) => ({ id: c.id, name: c.name }));
  });
}
