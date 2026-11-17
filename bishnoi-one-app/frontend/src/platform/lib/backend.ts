import type { ModuleDef } from "./modules";

// Bishnoi One's one backend (2026-11-17): every module's API in one server,
// each under its path (/platform, /crm, /inventory, /finance, /admin,
// /pharmacy, /in-licensing, /regulatory). BACKEND_URL is its address as this
// site's server reaches it: http://127.0.0.1:8300 on this computer, the
// backend's internal address on the server (e.g. http://10.0.1.1:8300).
// Only the Next server reads it; browsers never call the backend.

export const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:8300").replace(/\/+$/, "");

/** Bishnoi One Platform's API: the one sign-in (accounts), announcements, the Admin Console. */
export const PLATFORM_API = `${BACKEND_URL}/platform`;

/** A module's API address: BACKEND_URL + its path. */
export const moduleApiAddress = (m: Pick<ModuleDef, "apiPath">): string => `${BACKEND_URL}${m.apiPath}`;
