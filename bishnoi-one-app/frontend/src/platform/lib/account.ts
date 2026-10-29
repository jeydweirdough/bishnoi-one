import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";
import { ACCOUNT_COOKIE } from "./session-cookie";
import { siteOrigin } from "./site";

// The Bishnoi One account, on Bishnoi One Platform's API (/identity/...): the
// one sign-in for every module. Only the Next server talks to it, with the
// account's token from its httpOnly cookie.

export const PLATFORM_API = (process.env.PLATFORM_API_URL ?? "http://127.0.0.1:8305").replace(/\/$/, "");

// Where this site is: a module's pass names it as the return. ONE_APP_URL when
// set; else the address it was reached at (decided 2026-10-27: nothing to set),
// which the Platform accepts when it's an application's address in Applications.
export const oneAppUrl = siteOrigin;

export class AccountError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function accountCall<T>(path: string, body?: unknown, token?: string | null, forwardedFor?: string | null): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${PLATFORM_API}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(forwardedFor ? { "X-Forwarded-For": forwardedFor } : {}),
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new AccountError(503, "Bishnoi One can't be reached right now. Check the connection and try again.");
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new AccountError(response.status, typeof data?.detail === "string" ? data.detail : "Something went wrong. Try again.");
  return data as T;
}

/**
 * A change on the Platform with the signed-in account (GET, POST, PUT, PATCH,
 * DELETE). A refusal comes back as the kit's ApiError, detail and all, so a
 * form shows it field by field (src/platform/lib/result.ts).
 */
export async function accountSend<T>(method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE", path: string, body?: unknown): Promise<T> {
  const { ApiError } = await import("./api");
  const token = await accountToken();
  let response: Response;
  try {
    response = await fetch(`${PLATFORM_API}${path}`, {
      method,
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new ApiError(503, "Bishnoi One can't be reached right now. Check the connection and try again.");
  }
  if (response.status === 401) redirect("/login?expired=1");
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, data?.detail ?? "Something went wrong. Try again.");
  return data as T;
}

export async function accountToken(): Promise<string | null> {
  return (await cookies()).get(ACCOUNT_COOKIE)?.value ?? null;
}

/** Who is signed in to Bishnoi One (Platform's /identity/me). */
export type Account = {
  id: string;
  email: string;
  fullName: string;
  title: string | null;
  isCompanyAdmin: boolean;
  /** Also Bishnoi One staff (same email): "admin" (Platform Admin) or "member" (Support); null otherwise. */
  staff?: "admin" | "member" | null;
  company: { id: string; name: string; slug: string } | null;
  companies: { id: string; name: string; slug: string; current: boolean }[];
  /** The applications given to them, that their company has: a module each (by its Platform key). */
  apps: { key: string; name: string; appUrl: string | null; role: string | null; isAppAdmin: boolean; grantedAt?: string | null }[];
  /** The company's app catalogue (step 6): "app:purchasing", "inventory.batches"… on or off. */
  features?: Record<string, boolean>;
};

/**
 * The signed-in account, once per request. No account, or one that has ended,
 * goes to the sign-in page (the proxy already keeps pages from those with no cookie).
 */
export const getAccount = cache(async (): Promise<Account> => {
  const token = await accountToken();
  if (!token) redirect("/login");
  try {
    return await accountCall<Account>("/identity/me", undefined, token);
  } catch (error) {
    if (error instanceof AccountError && error.status === 401) redirect("/login?expired=1");
    throw error;
  }
});
