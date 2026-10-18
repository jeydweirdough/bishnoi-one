"use server";

// The application registry, deployments and integrations. Platform Admins
// change them; running a health check is anyone's (app/routers/applications.py).

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";
import type { Application, Deployment, Integration } from "../lib/types";

export type ApplicationInput = {
  key: string;
  name: string;
  description?: string | null;
  appUrl?: string | null;
  apiUrl?: string | null;
  healthUrl?: string | null;
  version?: string | null;
};

export type ApplicationPatch = Partial<Omit<ApplicationInput, "key">> & {
  isActive?: boolean;
  statusOverride?: Application["statusOverride"];
  statusNote?: string | null;
  sortOrder?: number;
};

export async function addApplication(input: ApplicationInput): Promise<Result<Application>> {
  return attempt(async () => {
    const body = await api.post<{ application: Application }>("/platform/applications", input);
    refresh();
    return body.application;
  });
}

export async function updateApplication(id: string, patch: ApplicationPatch): Promise<Result> {
  return attempt(async () => {
    await api.patch(`/platform/applications/${enc(id)}`, patch);
    refresh();
    return null;
  });
}

export async function addDeployment(
  appId: string,
  input: { version: string; environment: Deployment["environment"]; notes?: string | null },
): Promise<Result> {
  return attempt(async () => {
    await api.post(`/platform/applications/${enc(appId)}/deployments`, input);
    refresh();
    return null;
  });
}

export type IntegrationInput = { name: string; target?: string | null; healthUrl?: string | null; status?: Integration["status"]; notes?: string | null };

export async function addIntegration(appId: string, input: IntegrationInput): Promise<Result> {
  return attempt(async () => {
    await api.post(`/platform/applications/${enc(appId)}/integrations`, input);
    refresh();
    return null;
  });
}

export async function updateIntegration(id: string, patch: Partial<IntegrationInput>): Promise<Result> {
  return attempt(async () => {
    await api.patch(`/platform/integrations/${enc(id)}`, patch);
    refresh();
    return null;
  });
}

export async function deleteIntegration(id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`/platform/integrations/${enc(id)}`);
    refresh();
    return null;
  });
}

/** Asks every application whether it is up, now rather than when it's due. */
export async function checkNow(): Promise<Result> {
  return attempt(async () => {
    await api.get("/platform/monitoring?refresh=true");
    refresh();
    return null;
  });
}
