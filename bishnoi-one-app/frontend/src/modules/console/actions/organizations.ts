"use server";

// Companies, their departments and branches, and which applications each has.
// Platform Admins only; the API refuses anyone else (app/routers/companies.py).

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/console/platform/lib/api";
import { attempt, type Result } from "@/src/modules/console/platform/lib/result";
import type { Company, Unit } from "@/src/modules/console/lib/types";

export type CompanyInput = {
  name: string;
  slug?: string | null;
  currency: string;
  timezone: string;
  contactEmail?: string | null;
  notes?: string | null;
  applicationIds: string[];
  adminName?: string | null;
  adminEmail?: string | null;
};

export async function addCompany(input: CompanyInput): Promise<Result<Company>> {
  return attempt(async () => {
    const body = await api.post<{ company: Company }>("/platform/companies", input);
    refresh();
    return body.company;
  });
}

export type CompanyPatch = Partial<Omit<CompanyInput, "applicationIds" | "adminName" | "adminEmail">> & { status?: Company["status"] };

export async function updateCompany(id: string, patch: CompanyPatch): Promise<Result> {
  return attempt(async () => {
    await api.patch(`/platform/companies/${enc(id)}`, patch);
    refresh();
    return null;
  });
}

export type AppsChange = { added: number; removed: number; withdrawnFromPeople: number };

export async function setCompanyApplications(id: string, applicationIds: string[]): Promise<Result<AppsChange>> {
  return attempt(async () => {
    const body = await api.put<AppsChange>(`/platform/companies/${enc(id)}/applications`, { applicationIds });
    refresh();
    return body;
  });
}

export async function addUnit(companyId: string, unit: { kind: Unit["kind"]; name: string; location?: string | null }): Promise<Result> {
  return attempt(async () => {
    await api.post(`/platform/companies/${enc(companyId)}/units`, unit);
    refresh();
    return null;
  });
}

export async function updateUnit(companyId: string, unitId: string, patch: { name?: string; location?: string | null }): Promise<Result> {
  return attempt(async () => {
    await api.patch(`/platform/companies/${enc(companyId)}/units/${enc(unitId)}`, patch);
    refresh();
    return null;
  });
}

export async function deleteUnit(companyId: string, unitId: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/platform/companies/${enc(companyId)}/units/${enc(unitId)}`);
    refresh();
    return null;
  });
}
