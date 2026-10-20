"use server";

import { cookies } from "next/headers";
import { SECURE_COOKIE } from "@/src/platform/lib/session-cookie";
import { redirect } from "next/navigation";
import { ACCOUNT_COOKIE, AccountError, accountCall, accountToken, goLink, withPass, type AccountMe } from "./account";

export type GoState = { error?: string; email?: string } | null;

/** Signs in to the Bishnoi One account, then goes on to the application with a pass. */
export async function signInAccount(_previous: GoState, form: FormData): Promise<GoState> {
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  const app = String(form.get("app") ?? "");
  const returnTo = String(form.get("return") ?? "");
  const company = String(form.get("company") ?? "");
  if (!email || !password) return { error: "Enter your email and password.", email };
  let session: { accessToken: string; expiresIn: number };
  try {
    session = await accountCall("/identity/login", { email, password });
  } catch (e) {
    return { error: e instanceof AccountError ? e.message : "Signing in didn't work. Try again.", email };
  }
  (await cookies()).set(ACCOUNT_COOKIE, session.accessToken, {
    httpOnly: true,
    sameSite: "lax",
    secure: SECURE_COOKIE,
    path: "/",
    maxAge: session.expiresIn,
  });
  // More than one company of theirs, and the link doesn't say: they pick (the page asks).
  if (!company) {
    const me = await accountCall<AccountMe>("/identity/me", undefined, session.accessToken).catch(() => null);
    if (me && me.companies.length > 1) redirect(goLink(app, returnTo));
  }
  let target: string;
  try {
    const made = await accountCall<{ pass: string; returnTo: string }>("/identity/pass", { app, returnTo, ...(company ? { company } : {}) }, session.accessToken);
    target = withPass(made.returnTo, made.pass);
  } catch (e) {
    return { error: e instanceof AccountError ? e.message : "Opening the application didn't work. Try again.", email };
  }
  redirect(target);
}

/** Signs out of the Bishnoi One account on this browser, to sign in as someone else. */
export async function signOutAccount(form: FormData): Promise<void> {
  const token = await accountToken();
  if (token) await accountCall("/identity/logout", {}, token).catch(() => undefined);
  (await cookies()).delete(ACCOUNT_COOKIE);
  const app = String(form.get("app") ?? "");
  const returnTo = String(form.get("return") ?? "");
  redirect(goLink(app, returnTo));
}
