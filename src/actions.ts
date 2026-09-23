"use server";

// The platform's own actions: the companies on Orbit, and taking a new one
// on. Only a Developer Admin reaches these — the tier is not a role, so
// nothing a company does can get at them (api app/platform.py).

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { CompanyPerson, NewCompanyInput, PlatformCompany } from "@/src/platform/lib/types";

export async function addCompany(input: NewCompanyInput): Promise<Result<{ company: PlatformCompany }>> {
  return attempt(async () => {
    const made = await api.post<{ company: PlatformCompany }>("/platform/companies", input);
    refresh();
    return made;
  });
}

export async function setCompanyOn(orgId: string, on: boolean): Promise<Result> {
  return attempt(async () => {
    await api.patch(`/platform/companies/${enc(orgId)}?on=${on ? "true" : "false"}`, {});
    refresh();
    return null;
  });
}

/** Who is in one company, whoever runs it first. Developer Admins only. */
export async function companyPeople(orgId: string): Promise<Result<CompanyPerson[]>> {
  return attempt(async () => {
    const body = await api.get<{ people: CompanyPerson[] }>(`/platform/companies/${enc(orgId)}/people`);
    return body.people;
  });
}
