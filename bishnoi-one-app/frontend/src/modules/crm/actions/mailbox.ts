"use server";

import { refresh } from "next/cache";
import { api } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { ActivityItem } from "@/src/platform/lib/types";

// The person's own mailbox (Account → Mailbox) and sending from it. The API
// keeps the secrets; the screens only ever see the address.

export type MailAccount = { id: string; provider: string; providerName: string; address: string; isDefault: boolean; connectedAt: string; lastError: string | null };

export type MailboxInfo = {
  /** The person's mailboxes, the default first. */
  mailboxes: MailAccount[];
  providers: { key: "gmail" | "outlook" | "zoho_mail"; name: string; ready: boolean }[];
};

/** What connecting an address takes: a sign-in button, or a password with the server already known. */
export type MailboxDetect = {
  address: string;
  provider: string | null;
  name: string;
  signIn: "gmail" | "outlook" | "zoho_mail" | null;
  smtp: { host: string; port: number; security: "starttls" | "ssl" | "none"; guessed: boolean };
  help: { url: string; steps: string[] } | null;
};

export async function detectMailbox(address: string): Promise<Result<MailboxDetect>> {
  return attempt(() => api.get<MailboxDetect>(`/mailbox/detect?address=${encodeURIComponent(address)}`));
}

/** Where to send the person to sign in with their provider. */
export async function startMailbox(provider: "gmail" | "outlook" | "zoho_mail"): Promise<Result<{ url: string }>> {
  return attempt(() => api.post<{ url: string }>("/mailbox/start", { provider }));
}

export async function connectSmtp(input: { address: string; host: string; port: number; security: "starttls" | "ssl" | "none"; username: string; password: string }): Promise<Result<MailboxInfo>> {
  return attempt(async () => {
    const r = await api.put<MailboxInfo>("/mailbox/smtp", input);
    refresh();
    return r;
  });
}

export async function makeDefaultMailbox(id: string): Promise<Result<MailboxInfo>> {
  return attempt(async () => {
    const r = await api.put<MailboxInfo>(`/mailbox/${encodeURIComponent(id)}/default`, {});
    refresh();
    return r;
  });
}

export async function disconnectMailbox(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/mailbox/${encodeURIComponent(id)}`);
    refresh();
    return null;
  });
}

export async function readMailbox(): Promise<MailboxInfo | null> {
  return api.get<MailboxInfo>("/mailbox").catch(() => null);
}

export type EmailDraft = { companyId: string | null; contactId: string | null; to: string[]; templateId?: string; note?: string; subject?: string; body?: string };

/** The email exactly as it should be sent, to copy into the person's own email app. */
export async function prepareEmail(input: EmailDraft): Promise<Result<{ to: string[]; subject: string; body: string }>> {
  return attempt(() => api.post<{ to: string[]; subject: string; body: string }>("/email/prepare", input));
}

/** An email sent from the person's own email app, logged on the customer with a screenshot of it sent. */
export async function logEmail(input: EmailDraft, proof: FormData): Promise<Result<ActivityItem>> {
  return attempt(async () => {
    proof.set("email", JSON.stringify(input));
    const r = await api.upload<ActivityItem>("/email/log", proof);
    refresh();
    return r;
  });
}

/** Sends from the person's own mailbox; kept on the customer as an email. */
export async function sendEmail(input: { companyId: string | null; contactId: string | null; to: string[]; mailboxId?: string; subject?: string; body?: string; templateId?: string; note?: string }): Promise<Result<ActivityItem>> {
  return attempt(async () => {
    const r = await api.post<ActivityItem>("/email/send", input);
    refresh();
    return r;
  });
}

// --- email templates: written by an administrator, sent by reps as written ---

export type EmailTemplate = {
  id: string;
  name: string;
  subject: string;
  body: string;
  onlyTeams: string[];
  approvedOn: string;
  expiresOn: string | null;
  isActive: boolean;
  isCurrent: boolean;
};

export async function listTemplates(): Promise<EmailTemplate[]> {
  return api.get<EmailTemplate[]>("/email-templates").catch(() => []);
}

export type TemplateInput = Omit<EmailTemplate, "id" | "isCurrent">;

export async function saveTemplate(id: string | null, input: TemplateInput): Promise<Result<EmailTemplate>> {
  return attempt(async () => {
    const r = id ? await api.put<EmailTemplate>(`/admin/email-templates/${encodeURIComponent(id)}`, input) : await api.post<EmailTemplate>("/admin/email-templates", input);
    refresh();
    return r;
  });
}

/** A customer's own address and their contacts' addresses, to pick who an email is to. */
export async function customerAddresses(companyId: string): Promise<{ name: string; email: string | null; contacts: { id: string; name: string; email: string | null }[] } | null> {
  return api
    .get<{ name: string; email: string | null; contacts: { id: string; name: string; email: string | null }[] }>(`/crm/customers/${encodeURIComponent(companyId)}`)
    .then((c) => ({ name: c.name, email: c.email, contacts: c.contacts }))
    .catch(() => null);
}

/** Emails sent from the CRM: one's own, or everyone's one reaches. */
export async function sentEmails(who: "me" | "all", q: string, offset: number): Promise<{ items: ActivityItem[]; total: number }> {
  const query = new URLSearchParams({ who, offset: String(offset), limit: "50", ...(q.trim() && { q: q.trim() }) });
  return api.get<{ items: ActivityItem[]; total: number }>(`/emails?${query}`).catch(() => ({ items: [], total: 0 }));
}
