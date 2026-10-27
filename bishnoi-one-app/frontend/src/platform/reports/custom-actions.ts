"use server";

import { revalidatePath } from "next/cache";
import { accountSend } from "../lib/account";
import { apiFor } from "../lib/api";
import type { ModuleKey } from "../lib/modules";
import { attempt, type Result } from "../lib/result";
import type { Definition, SavedReport } from "./custom";
import type { ReportData } from "./types";

// Saving, changing and removing a built report, on the Platform (app/routers/saved_reports.py):
// one place for every module's saved reports.

const enc = encodeURIComponent;

export async function saveReport(input: { app: string; baseKey: string; name: string; definition: Definition; shared: boolean }): Promise<Result<SavedReport>> {
  return attempt(async () => {
    const saved = await accountSend<SavedReport>("POST", "/identity/reports", input);
    revalidatePath("/", "layout");
    return saved;
  });
}

export async function changeReport(id: string, change: { name?: string; definition?: Definition; shared?: boolean }): Promise<Result<SavedReport>> {
  return attempt(async () => {
    const saved = await accountSend<SavedReport>("PATCH", `/identity/reports/${enc(id)}`, change);
    revalidatePath("/", "layout");
    return saved;
  });
}

export async function deleteReport(id: string): Promise<Result> {
  return attempt(async () => {
    await accountSend("DELETE", `/identity/reports/${enc(id)}`);
    revalidatePath("/", "layout");
    return null;
  });
}

export async function listSavedReports(app: string): Promise<SavedReport[]> {
  try {
    return await accountSend<SavedReport[]>("GET", `/identity/reports?app=${enc(app)}`);
  } catch {
    return [];
  }
}

export async function readSavedReport(id: string): Promise<SavedReport | null> {
  try {
    return await accountSend<SavedReport>("GET", `/identity/reports/${enc(id)}`);
  } catch {
    return null;
  }
}

export async function fetchBaseReport(app: string, baseKey: string): Promise<Result<ReportData>> {
  return attempt(async () => {
    const key = enc(baseKey);
    const mod = app.toLowerCase() as ModuleKey;
    if (mod === "inventory") {
      return await apiFor("inventory").get<ReportData>(`/inventory/reports/${key}`);
    }
    if (mod === "finance") {
      return await apiFor("finance").get<ReportData>(`/finance/reports/${key}`);
    }
    if (mod === "crm") {
      return await apiFor("crm").get<ReportData>(`/reports/${key}`);
    }
    if (mod === "pharmacy") {
      return await apiFor("pharmacy").get<ReportData>(`/reports/${key}`);
    }
    if (mod === "admin") {
      return await apiFor("admin").get<ReportData>(`/admin/reports/${key}`);
    }
    return await apiFor(mod).get<ReportData>(`/reports/${key}`);
  });
}
