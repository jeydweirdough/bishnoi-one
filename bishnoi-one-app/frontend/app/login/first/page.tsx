import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { accountCall, accountToken, type Account } from "@/src/platform/lib/account";
import { SignInShell } from "@/src/one/sign-in-shell";
import { FirstSteps } from "@/src/one/first-steps";

export const metadata: Metadata = { title: "Before you start · Bishnoi One" };

type Search = Promise<Record<string, string | string[] | undefined>>;

/**
 * Before anything else (2026-10-30): a password someone handed over is changed for one's own, and
 * administrators set up two-step sign-in where it's required. The one app sends them here until done.
 */
export default async function FirstSignInPage({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  const asked = typeof q.next === "string" ? q.next : "/";
  const next = asked.startsWith("/") && !asked.startsWith("//") && !asked.startsWith("/login") ? asked : "/";
  const token = await accountToken();
  const me = token ? await accountCall<Account>("/identity/me", undefined, token).catch(() => null) : null;
  if (!me) redirect("/login");
  const password = Boolean(me.mustChangePassword);
  const twoStep = Boolean(me.twoStep?.needed);
  if (!password && !twoStep) redirect(next);
  return (
    <SignInShell
      title={password ? "Choose your own password" : "Set up two-step sign-in"}
      intro={
        password
          ? "You signed in with a password someone gave you. Choose your own before you start: only you will know it."
          : "As an administrator, your sign-in needs a second step: a code from an app on your phone. It takes a minute."
      }
    >
      <FirstSteps password={password} twoStep={twoStep} next={next} />
    </SignInShell>
  );
}
