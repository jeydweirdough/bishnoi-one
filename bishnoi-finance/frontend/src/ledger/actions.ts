"use server";

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Account, AccountType, Entry, Posting } from "./types";

// The ledger. The API checks every entry balances, and that only admins change
// the chart and the posting accounts.

export type AccountInput = { code: string; name: string; type: AccountType; description: string | null; isActive: boolean };

export async function saveAccount(id: string | null, input: AccountInput): Promise<Result<Account>> {
  return attempt(async () => {
    const saved = id ? await api.put<Account>(`/finance/ledger/accounts/${enc(id)}`, input) : await api.post<Account>("/finance/ledger/accounts", input);
    refresh();
    return saved;
  });
}

export type EntryInput = {
  date: string;
  memo: string;
  reference: string | null;
  lines: { accountId: string; debitCentavos: number; creditCentavos: number; description: string | null }[];
};

export async function postEntry(input: EntryInput): Promise<Result<Entry>> {
  return attempt(async () => {
    const posted = await api.post<Entry>("/finance/ledger/entries", input);
    refresh();
    return posted;
  });
}

export async function reverseEntry(id: string): Promise<Result<Entry>> {
  return attempt(async () => {
    const posted = await api.post<Entry>(`/finance/ledger/entries/${enc(id)}/reverse`, {});
    refresh();
    return posted;
  });
}

/** Approve or reject an entry waiting for approval. If someone else decided it a moment
 *  earlier, the API says who and when; the page is redrawn either way, so it shows the
 *  entry as it now stands. */
export async function decideEntry(id: string, decision: "approve" | "reject", reason: string | null): Promise<Result<Entry>> {
  const result = await attempt(() =>
    decision === "approve"
      ? api.post<Entry>(`/finance/ledger/entries/${enc(id)}/approve`, {})
      : api.post<Entry>(`/finance/ledger/entries/${enc(id)}/reject`, { reason }),
  );
  refresh();
  return result;
}

export async function savePosting(accounts: Record<string, string | null>): Promise<Result<Posting>> {
  return attempt(async () => {
    const saved = await api.put<Posting>("/finance/ledger/posting", { accounts });
    refresh();
    return saved;
  });
}
