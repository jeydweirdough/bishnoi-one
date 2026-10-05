"use server";

// The applications a company has, for the user forms: someone can only be
// given what their company has, so the form asks when the company changes.

import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { CompanyDetail } from "../../lib/types";

export type CompanyApp = CompanyDetail["applications"][number];

export async function companyApplications(companyId: string): Promise<Result<CompanyApp[]>> {
  return attempt(async () => {
    const body = await api.get<{ company: CompanyDetail }>(`/platform/companies/${enc(companyId)}`);
    return body.company.applications;
  });
}
