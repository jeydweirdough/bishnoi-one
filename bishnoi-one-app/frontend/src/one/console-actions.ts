"use server";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { AccountError, accountCall } from "@/src/platform/lib/account";
import { cookieOptions, moduleCookie } from "@/src/platform/lib/session-cookie";
import type { SignInState } from "./actions";

// The Platform console's own sign-in, for Bishnoi One's staff (decided
// 2026-10-24: the console moved into the one app, its staff accounts kept).
// Their session is the console module's cookie, nothing else's.

const COOKIE = moduleCookie("console");
const onConsole = (next: string) => (next.startsWith("/platform/console") && !next.startsWith("//") ? next : "/platform/console");

export async function consoleSignIn(_previous: SignInState, form: FormData): Promise<SignInState> {
  const email = String(form.get("email") ?? "").trim();
  const password = String(form.get("password") ?? "");
  const next = onConsole(String(form.get("next") ?? ""));
  if (!email || !password) return { error: "Enter your email and password.", email };
  const jar = await cookies();
  // Whoever was signed in to the console here is signed out first.
  const before = jar.get(COOKIE)?.value;
  if (before) await accountCall("/auth/logout", {}, before).catch(() => undefined);
  jar.delete(COOKIE);
  try {
    const forwarded = (await headers()).get("x-forwarded-for")?.split(",")[0].trim() || null;
    const session = await accountCall<{ accessToken: string; expiresIn: number }>("/auth/login", { email, password }, null, forwarded);
    jar.set(COOKIE, session.accessToken, cookieOptions(session.expiresIn));
  } catch (e) {
    return { error: e instanceof AccountError ? e.message : "Signing in didn't work. Try again.", email };
  }
  return { go: next };
}

export async function consoleSignOut(): Promise<void> {
  const jar = await cookies();
  const token = jar.get(COOKIE)?.value;
  if (token) await accountCall("/auth/logout", {}, token).catch(() => undefined);
  jar.delete(COOKIE);
  redirect("/platform/console/login");
}

/** A staff member's own password (the console's /auth/password, with the console's session). */
export async function consoleChangePassword(current: string, next: string): Promise<{ ok: true; data: null } | { ok: false; error: string; fields?: Record<string, string> }> {
  const { api } = await import("@/src/platform/lib/api");
  const { toFailure } = await import("@/src/platform/lib/result");
  try {
    await api.post("/auth/password", { currentPassword: current, newPassword: next });
    return { ok: true, data: null };
  } catch (error) {
    return toFailure(error);
  }
}
