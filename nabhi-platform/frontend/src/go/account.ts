import "server-only";
import { cookies } from "next/headers";

// Nabhi accounts (the companies' people), apart from the console's staff
// sign-in: their own cookie, sent to the API's /identity endpoints only.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";
export const ACCOUNT_COOKIE = "nabhi_account";

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
    throw new AccountError(503, "Nabhi can't be reached right now. Check the internet connection and try again.");
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

/** Where a pass goes: the application's return address, with the pass added. */
export function withPass(returnTo: string, pass: string): string {
  return `${returnTo}?pass=${encodeURIComponent(pass)}`;
}
