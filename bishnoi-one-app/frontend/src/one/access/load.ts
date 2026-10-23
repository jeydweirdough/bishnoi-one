import "server-only";
import { cache } from "react";
import { accountSend } from "@/src/platform/lib/account";
import { ApiError } from "@/src/platform/lib/api";
import type { AccessData } from "./types";

/** The company's access, as its administrator sees it; null for anyone else (once per request). */
export const loadAccess = cache(async (): Promise<AccessData | null> => {
  try {
    return await accountSend<AccessData>("GET", "/identity/access");
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) return null;
    throw error;
  }
});
