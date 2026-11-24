import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { SignInShell } from "@/src/one/sign-in-shell";
import { accountCall, accountToken, type Account } from "@/src/platform/lib/account";
import { LoginForm } from "@/src/one/login-form";

export const metadata: Metadata = { title: "Sign in to Bishnoi One" };

type Search = Promise<Record<string, string | string[] | undefined>>;


/**
 * The one app's sign-in (decided 2026-10-23): one Bishnoi One account for every
 * module. Someone already signed in goes straight on.
 */
export default async function LoginPage({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  const asked = typeof q.next === "string" ? q.next : "/";
  const next = asked.startsWith("/") && !asked.startsWith("//") ? asked : "/";
  const expired = q.expired === "1";

  // A new Bishnoi One with nobody in it yet: set it up first (app/setup).
  const setup = await accountCall<{ needed: boolean }>("/setup").catch(() => null);
  if (setup?.needed) redirect("/setup");

  const token = await accountToken();
  if (token) {
    const me = await accountCall<Account>("/identity/me", undefined, token).catch(() => null);
    if (me) redirect(next);
  }

  // Studio Admin's two-column login (2026-11-19): src/one/sign-in-shell.tsx.
  return (
    <SignInShell title="Sign in to your account" intro="Enter your work email and password.">
      {expired && <p className="rounded-lg bg-muted px-4 py-2.5 text-center text-sm text-muted-foreground">Your session ended. Sign in again to pick up where you left off.</p>}
      <LoginForm next={next} email={typeof q.email === "string" ? q.email : ""} />
    </SignInShell>
  );
}
