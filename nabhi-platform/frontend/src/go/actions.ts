"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ACCOUNT_COOKIE, AccountError, accountCall, accountToken, withPass } from "./account";

export type GoState = { error?: string; email?: string } | null;

/** Signs in to the Nabhi account, then goes on to the application with a pass. */
export async function signInAccount(_previous: GoState, form: FormData): Promise<GoState> {
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  const app = String(form.get("app") ?? "");
  const returnTo = String(form.get("return") ?? "");
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
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: session.expiresIn,
  });
  let target: string;
  try {
    const made = await accountCall<{ pass: string; returnTo: string }>("/identity/pass", { app, returnTo }, session.accessToken);
    target = withPass(made.returnTo, made.pass);
  } catch (e) {
    return { error: e instanceof AccountError ? e.message : "Opening the application didn't work. Try again.", email };
  }
  redirect(target);
}

/** Signs out of the Nabhi account on this browser, to sign in as someone else. */
export async function signOutAccount(form: FormData): Promise<void> {
  const token = await accountToken();
  if (token) await accountCall("/identity/logout", {}, token).catch(() => undefined);
  (await cookies()).delete(ACCOUNT_COOKIE);
  const app = String(form.get("app") ?? "");
  const returnTo = String(form.get("return") ?? "");
  redirect(`/go?app=${encodeURIComponent(app)}&return=${encodeURIComponent(returnTo)}`);
}
