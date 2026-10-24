"use server";

import { refresh } from "next/cache";
import { api } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

// Find leads with AI: what a chatbot found, checked and saved by the API
// (customers.create; saved as the person's customers in their team).

export type Lead = {
  name: string;
  type?: string | null;
  address?: string | null;
  city?: string | null;
  region?: string | null;
  phone?: string | null;
  email?: string | null;
  website?: string | null;
  source?: string | null;
  why?: string | null;
};

export type LeadCheck = {
  index: number;
  type: string | null;
  problems: string[];
  matches: { id: string | null; name: string; teamName: string | null; why: string[]; points: number }[];
};

export async function checkLeads(leads: Lead[]): Promise<Result<LeadCheck[]>> {
  return attempt(async () => (await api.post<{ items: LeadCheck[] }>("/leads/check", { leads })).items);
}

export async function saveLeads(leads: Lead[]): Promise<Result<{ saved: { index: number; id: string; name: string }[]; skipped: { index: number; name: string; why: string }[] }>> {
  return attempt(async () => {
    const r = await api.post<{ saved: { index: number; id: string; name: string }[]; skipped: { index: number; name: string; why: string }[] }>("/leads/save", { leads });
    refresh();
    return r;
  });
}
