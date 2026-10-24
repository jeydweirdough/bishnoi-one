"use server";

// A company's outside services (app/routers/services.py): Zoho Books and the
// email providers, given to the applications that use them. Platform Admins change them.

import { refresh } from "next/cache";
import { api, enc } from "@/src/modules/console/platform/lib/api";
import { attempt, type Result } from "@/src/modules/console/platform/lib/result";

export type ServiceDetail = {
  key: string;
  label: string;
  hint: string;
  secret: boolean;
  required: boolean;
  options: { value: string; label: string }[];
  /** Not secret: what's saved. */
  value?: string | null;
  /** Secret: whether one is saved, and its last four characters (empty when it's short). */
  saved?: boolean;
  ending?: string;
};

export type ServiceInfo = {
  key: string;
  name: string;
  purpose: string;
  helpUrl: string;
  /** The applications that use it, by key. */
  apps: string[];
  enabled: boolean;
  details: ServiceDetail[];
  missing: string[];
  /** Saved with an earlier signing key of the platform's: the secrets have to be typed in again. */
  unreadable: boolean;
  check: { at: string; ok: boolean; message: string } | null;
  updatedAt: string | null;
  updatedBy: { id: string; name: string } | null;
};

/** Saves what changed. A secret left out stays as saved; one sent as "" is removed. */
export async function saveService(companyId: string, key: string, values: Record<string, string>, enabled?: boolean): Promise<Result<ServiceInfo>> {
  return attempt(async () => {
    const saved = await api.put<ServiceInfo>(`/platform/companies/${enc(companyId)}/services/${enc(key)}`, { values, enabled });
    refresh();
    return saved;
  });
}

/** Tries the saved details on the service; the answer is kept and shown. */
export async function checkService(companyId: string, key: string): Promise<Result<ServiceInfo>> {
  return attempt(async () => {
    const checked = await api.post<ServiceInfo>(`/platform/companies/${enc(companyId)}/services/${enc(key)}/check`, {});
    refresh();
    return checked;
  });
}
