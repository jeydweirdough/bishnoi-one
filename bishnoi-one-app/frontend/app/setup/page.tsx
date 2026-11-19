import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { accountCall } from "@/src/platform/lib/account";
import { SignInShell } from "@/src/one/sign-in-shell";
import { SetupForm } from "@/src/one/setup-form";

export const metadata: Metadata = { title: "Set up Bishnoi One" };

/**
 * The first run (decided 2026-10-27): while nobody has an account, the company
 * and its first administrator are made here. Once anyone has one, it's gone.
 */
export default async function SetupPage() {
  const state = await accountCall<{ needed: boolean }>("/setup").catch(() => null);
  if (!state?.needed) redirect("/login");

  return (
    <SignInShell home="/setup" title="Set up Bishnoi One" intro="Your company and its first administrator. You can add everyone else afterwards.">
      <SetupForm />
    </SignInShell>
  );
}
