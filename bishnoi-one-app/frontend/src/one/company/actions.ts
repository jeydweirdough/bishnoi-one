"use server";

import { revalidatePath } from "next/cache";
import type { ServiceInfo } from "@/src/modules/console/actions/services";
import { accountSend } from "@/src/platform/lib/account";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { CatalogueEntry, CompanyProfile } from "./types";

// A company administrator's changes to their own company, on Bishnoi One Platform
// (/identity/company, feature plan step 5).

const enc = encodeURIComponent;
const refresh = () => revalidatePath("/platform", "layout");

export async function changeCompany(change: Partial<Pick<CompanyProfile, "name" | "contactEmail" | "timezone" | "currency">>): Promise<Result<{ company: CompanyProfile }>> {
  return attempt(async () => {
    const saved = await accountSend<{ company: CompanyProfile }>("PATCH", "/identity/company", change);
    refresh();
    return saved;
  });
}

export async function saveOwnService(key: string, values: Record<string, string>, enabled?: boolean): Promise<Result<ServiceInfo>> {
  return attempt(async () => {
    const saved = await accountSend<ServiceInfo>("PUT", `/identity/company/services/${enc(key)}`, { values, enabled });
    refresh();
    return saved;
  });
}

export async function checkOwnService(key: string): Promise<Result<ServiceInfo>> {
  return attempt(async () => {
    const checked = await accountSend<ServiceInfo>("POST", `/identity/company/services/${enc(key)}/check`, {});
    refresh();
    return checked;
  });
}

export async function signPersonOut(id: string): Promise<Result<{ ended: number }>> {
  return attempt(async () => {
    const r = await accountSend<{ ended: number }>("POST", `/identity/company/security/people/${enc(id)}/sign-out`, {});
    refresh();
    return r;
  });
}

/** A catalogue app (its key) or a feature ("inventory.batches"), on or off (step 6). */
export async function switchCatalogue(key: string, on: boolean): Promise<Result<{ apps: CatalogueEntry[] }>> {
  return attempt(async () => {
    const r = await accountSend<{ apps: CatalogueEntry[] }>("PUT", `/identity/company/catalogue/${enc(key)}`, { on });
    refresh();
    return r;
  });
}
