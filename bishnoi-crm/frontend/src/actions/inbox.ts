"use server";

import { refresh } from "next/cache";
import { api } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

// The lead inbox: what came in on the company's own channels (Facebook,
// Messenger, WhatsApp, Viber, Tawk.to, the website's forms), handled by the
// API (customers.inbox).

export type InboxChannel = "facebook" | "messenger" | "whatsapp" | "viber" | "tawkto" | "form";

export type InboxLead = {
  id: string;
  channel: InboxChannel;
  channelName: string;
  status: "new" | "added" | "dismissed";
  name: string;
  business: string | null;
  phone: string | null;
  email: string | null;
  city: string | null;
  lastMessage: string | null;
  messageCount: number;
  receivedAt: string;
  lastAt: string;
  company: { id: string; name: string } | null;
  handledBy: string | null;
  handledAt: string | null;
};

export type InboxPage = {
  items: InboxLead[];
  total: number;
  page: number;
  pageSize: number;
  counts: { new: number; added: number; dismissed: number };
  channels: { key: string; name: string; on: boolean; address: string }[];
  connected: boolean;
};

export type InboxDetail = InboxLead & {
  messages: { at: string | null; text: string | null }[];
  details: Record<string, string>;
  matches: { id: string | null; name: string; teamName: string | null; why: string[]; points: number }[];
  types: { code: string; name: string }[];
};

export async function getInboxLead(id: string): Promise<Result<InboxDetail>> {
  return attempt(() => api.get<InboxDetail>(`/inbox/${id}`));
}

export async function addInboxLead(id: string, input: { companyId?: string; name?: string; type?: string }): Promise<Result<{ companyId: string; companyName: string }>> {
  return attempt(async () => {
    const r = await api.post<{ companyId: string; companyName: string }>(`/inbox/${id}/add`, input);
    refresh();
    return r;
  });
}

export async function dismissInboxLead(id: string): Promise<Result<InboxLead>> {
  return attempt(async () => {
    const r = await api.post<InboxLead>(`/inbox/${id}/dismiss`, {});
    refresh();
    return r;
  });
}

export async function reopenInboxLead(id: string): Promise<Result<InboxLead>> {
  return attempt(async () => {
    const r = await api.post<InboxLead>(`/inbox/${id}/reopen`, {});
    refresh();
    return r;
  });
}
