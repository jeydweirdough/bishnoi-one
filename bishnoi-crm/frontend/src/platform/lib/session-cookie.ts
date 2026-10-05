// Each Bishnoi One app has its own accounts and its own sign-in, so each keeps its
// own cookie. With one shared name, signing in to one app on the same host
// (localhost in development) would sign you out of the others.
export const SESSION_COOKIE = `bishnoi_${(process.env.NEXT_PUBLIC_BISHNOI_APP ?? process.env.NEXT_PUBLIC_NABHI_APP) ?? "app"}_session`;

// The company last signed in to on this browser (its short name on Bishnoi One
// Platform), so the sign-in page can fill it in. Shared by every app: a person
// works for the same company in each. Signed in, the session says the company.
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
