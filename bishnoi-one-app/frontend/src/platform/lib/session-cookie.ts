// The one app's cookies (decided 2026-10-23). One person per browser by design:
// a single Bishnoi One account cookie, and under it one session per module,
// opened from it on first use (app/auth/enter/[module]) and dropped with it.

/** The Bishnoi One account: who is signed in to the one app. */
export const ACCOUNT_COOKIE = "bishnoi_account";

/** A module's own session with its API, opened from the account with a Platform pass. */
export const moduleCookie = (key: string) => `bishnoi_${key}_session`;

/** Whom an administrator is viewing a module as (decided 2026-10-26): "<id>|<name>|<role>", per module. */
export const viewAsCookie = (key: string) => `bishnoi_${key}_view_as`;
/** Sent to the module's API with that person's id; the API checks the sender may (app/platform_roles.py). */
export const VIEW_AS_HEADER = "X-Bishnoi-View-As";

/** Where the person was in a module, so an ended module session reopens and comes back there (app/auth/renew). */
export const HERE_COOKIE = "bishnoi_here";

// Set by the proxy from the path, never by the browser: which module a request
// is for, so the shared API client talks to that module's API with its session.
export const MODULE_HEADER = "x-bishnoi-module";

// The company last signed in to on this browser (its short name on Bishnoi One
// Platform). Signed in, the session says the company.
export const COMPANY_COOKIE = "bishnoi_company";
export const COMPANY_HEADER = "X-Bishnoi-Company";

/** A company's short name as the platform keeps it, or null when it isn't one. */
export function cleanCompany(value: unknown): string | null {
  const slug = typeof value === "string" ? value.trim().toLowerCase() : "";
  return /^[a-z0-9][a-z0-9-]{0,38}[a-z0-9]$/.test(slug) ? slug : null;
}

/** The company a session's token is for: what comes before its first dot. */
export function companyOfToken(token: string): string | null {
  return token.includes(".") ? cleanCompany(token.split(".", 1)[0]) : null;
}

// Online, sign-in cookies travel over HTTPS only. ALLOW_HTTP_SIGN_IN=true lets
// them over plain http too, for a server reached only inside the office until
// it has an HTTPS address. Never set it on a server the internet can reach.
export const SECURE_COOKIE = process.env.NODE_ENV === "production" && process.env.ALLOW_HTTP_SIGN_IN !== "true";

/** The options every sign-in cookie here is set with. */
export const cookieOptions = (maxAge: number) => ({ httpOnly: true, sameSite: "lax" as const, secure: SECURE_COOKIE, path: "/", maxAge });
