"use server";

// Deleting what a Platform Admin added: the API checks who may, and refuses
// what would break something (an application a company still has).

import { refresh } from "next/cache";
import { api, enc } from "@/src/platform/lib/api";
import { attempt, type Result } from "@/src/platform/lib/result";

export type Deletable = "company" | "application" | "deployment" | "incident" | "ticket" | "request";

const PATHS: Record<Deletable, string> = {
  company: "/platform/companies/",
  application: "/platform/applications/",
  deployment: "/platform/deployments/",
  incident: "/platform/incidents/",
  ticket: "/platform/tickets/",
  request: "/platform/access/requests/",
};

export async function deleteRecord(kind: Deletable, id: string): Promise<Result> {
  return attempt(async () => {
    await api.del(`${PATHS[kind]}${enc(id)}`);
    refresh();
    return null;
  });
}
