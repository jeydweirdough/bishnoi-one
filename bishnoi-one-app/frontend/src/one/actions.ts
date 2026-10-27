"use server";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { AccountError, PLATFORM_API, accountCall, accountToken } from "@/src/platform/lib/account";
import { MODULES } from "@/src/platform/lib/modules";
import { ACCOUNT_COOKIE, HERE_COOKIE, cookieOptions, moduleCookie, viewAsCookie } from "@/src/platform/lib/session-cookie";

// Signing in to the one app with the Bishnoi One account, signing out, and
// moving to another company. One person per browser: a new sign-in (or a new
// company) drops every module's session, so each opens again as them.

// After signing in, the browser itself goes on (`go`), not a server redirect: the
// next page may be a module's, whose session is opened by a redirect that sets a
// cookie (app/auth/enter), and only the browser keeps cookies across redirects
// (Next follows an action's redirect on the server, with no cookie jar).
export type SignInState = { error?: string; email?: string; go?: string } | null;

type Session = { accessToken: string; expiresIn: number };

/** Only a page of this site, never somewhere else. */
const onSite = (next: string) => (next.startsWith("/") && !next.startsWith("//") ? next : "/");

async function forwardedFor(): Promise<string | null> {
  return (await headers()).get("x-forwarded-for")?.split(",")[0].trim() || null;
}

/** Each module's session, and where they were, dropped: they open again from the account. */
async function dropModuleSessions(): Promise<void> {
  const jar = await cookies();
  for (const m of MODULES) {
    jar.delete(moduleCookie(m.key));
    jar.delete(viewAsCookie(m.key));
  }
  jar.delete(HERE_COOKIE);
}

export async function signIn(_previous: SignInState, form: FormData): Promise<SignInState> {
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  const next = onSite(String(form.get("next") ?? "/"));
  if (!email || !password) return { error: "Enter your email and password.", email };
  let session: Session;
  try {
    session = await accountCall<Session>("/identity/login", { email, password }, null, await forwardedFor());
  } catch (e) {
    return { error: e instanceof AccountError ? e.message : "Signing in didn't work. Try again.", email };
  }
  await dropModuleSessions();
  (await cookies()).set(ACCOUNT_COOKIE, session.accessToken, cookieOptions(session.expiresIn));
  return { go: next };
}

export async function signOut(): Promise<void> {
  const token = await accountToken();
  if (token) await accountCall("/identity/logout", {}, token).catch(() => undefined);
  await dropModuleSessions();
  (await cookies()).delete(ACCOUNT_COOKIE);
  redirect("/login");
}

/** To another company they work for: a new Bishnoi One sign-in there, and every module opens again at it. */
export async function switchCompany(form: FormData): Promise<void> {
  const company = String(form.get("company") ?? "");
  const token = await accountToken();
  if (!token) redirect("/login");
  let session: Session;
  try {
    session = await accountCall<Session>("/identity/switch", { company }, token, await forwardedFor());
  } catch (e) {
    redirect(`/?notice=${encodeURIComponent(e instanceof AccountError ? e.message : "Switching company didn't work.")}`);
  }
  await dropModuleSessions();
  (await cookies()).set(ACCOUNT_COOKIE, session.accessToken, cookieOptions(session.expiresIn));
  redirect("/");
}

export type PasswordResult = { ok: true; data: null } | { ok: false; error: string; fields?: Record<string, string> };

/**
 * A new password for the Bishnoi One account (the one sign-in for every module),
 * given the current one. Every module's profile asks here.
 */
export async function changePassword(current: string, next: string): Promise<PasswordResult> {
  const token = await accountToken();
  if (!token) return { ok: false, error: "Sign in again first." };
  try {
    await accountCall("/identity/password", { currentPassword: current, newPassword: next }, token);
    return { ok: true, data: null };
  } catch (e) {
    const error = e instanceof AccountError ? e.message : "Changing the password didn't work. Try again.";
    // The current password wrong: say so beside it.
    if (e instanceof AccountError && (e.status === 400 || e.status === 403) && /current/i.test(error)) return { ok: false, error, fields: { currentPassword: error } };
    return { ok: false, error };
  }
}

export type SetUpState = { error?: string; fields?: Record<string, string>; go?: string; values?: Record<string, string> } | null;

/**
 * The first run (decided 2026-10-27): the company and its first administrator,
 * made on the Platform with the setup code from its log, then signed in.
 */
export async function setUp(_previous: SetUpState, form: FormData): Promise<SetUpState> {
  const values = Object.fromEntries(["code", "companyName", "name", "email"].map((k) => [k, String(form.get(k) ?? "").trim()]));
  const password = String(form.get("password") ?? "");
  let response: Response;
  try {
    response = await fetch(`${PLATFORM_API}/setup`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...values, password }), cache: "no-store" });
  } catch {
    return { error: "Bishnoi One can't be reached right now. Check the connection and try again.", values };
  }
  if (!response.ok) {
    const detail = (await response.json().catch(() => null))?.detail;
    if (typeof detail === "string") return { error: detail, values };
    const fields: Record<string, string> = {};
    for (const e of Array.isArray(detail) ? detail : []) fields[String(e.loc?.at(-1))] = String(e.msg ?? "").replace(/^Value error, /, "");
    return { fields, error: Object.keys(fields).length ? undefined : "Setting up didn't work. Try again.", values };
  }
  try {
    const session = await accountCall<Session>("/identity/login", { email: values.email, password }, null, await forwardedFor());
    await dropModuleSessions();
    (await cookies()).set(ACCOUNT_COOKIE, session.accessToken, cookieOptions(session.expiresIn));
  } catch {
    return { go: "/login" };
  }
  return { go: "/" };
}
