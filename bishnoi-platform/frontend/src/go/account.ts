import "server-only";
import { cookies } from "next/headers";

// Bishnoi One accounts (the companies' people), apart from the console's staff
// sign-in: their own cookie, sent to the API's /identity endpoints only.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";
export const ACCOUNT_COOKIE = "bishnoi_account";

// One person per browser (decided 2026-10-21): whoever is signed in to Bishnoi
// One here, by their account's id, for every app to compare its own session
// with (their lib/session-cookie.ts). It has to reach the apps' addresses, so
// online it's set on their common parent domain, COOKIE_DOMAIN (for example
// .bishnoi-one.cloud-ip.cc); unset, it's this address's own, which on this
// computer is every app's too (localhost, whatever the port).
export const HOLDER_COOKIE = "bishnoi_holder";
export const HOLDER_DOMAIN = process.env.COOKIE_DOMAIN || undefined;

export class AccountError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function accountCall<T>(path: string, body?: unknown, token?: string | null): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new AccountError(503, "Bishnoi One can't be reached right now. Check the internet connection and try again.");
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : "Something went wrong. Try again.";
    throw new AccountError(response.status, detail);
  }
  return data as T;
}

export async function accountToken(): Promise<string | null> {
  return (await cookies()).get(ACCOUNT_COOKIE)?.value ?? null;
}

/** Who is signed in, as far as choosing a company goes. */
export type AccountMe = {
  email?: string;
  company: { slug: string; name: string } | null;
  companies: { slug: string; name: string; current: boolean }[];
  /** The applications they may open (given to them, and their company has it). */
  apps: { key: string; name: string; appUrl: string | null }[];
};

/** This page again, for one application and (when known) one company. */
export function goLink(app: string, returnTo: string, company?: string): string {
  return `/go?app=${encodeURIComponent(app)}&return=${encodeURIComponent(returnTo)}${company ? `&company=${encodeURIComponent(company)}` : ""}`;
}

/** Where a pass goes: the application's return address, with the pass added. */
export function withPass(returnTo: string, pass: string): string {
  return `${returnTo}?pass=${encodeURIComponent(pass)}`;
}
