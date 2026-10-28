import "server-only";
import { cache } from "react";
import { accountSend } from "@/src/platform/lib/account";
import { ApiError } from "@/src/platform/lib/api";
import type { OrgData } from "./types";

/** The company's org chart, as its administrator sees it; null for anyone else (once per request). */
export const loadOrganisation = cache(async (): Promise<OrgData | null> => {
  try {
    return await accountSend<OrgData>("GET", "/identity/organisation");
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) return null;
    throw error;
  }
});
