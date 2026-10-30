import type { Metadata } from "next";
import { SignInShell } from "@/src/one/sign-in-shell";
import { ForgotForm } from "@/src/one/sign-in-forms";

export const metadata: Metadata = { title: "Forgot your password · Bishnoi One" };

type Search = Promise<Record<string, string | string[] | undefined>>;

/** Forgot password (2026-10-30): a link by email to choose a new one. */
export default async function ForgotPage({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  return (
    <SignInShell title="Forgot your password?" intro="Enter your work email. We'll send a link to choose a new password.">
      <ForgotForm email={typeof q.email === "string" ? q.email : ""} />
    </SignInShell>
  );
}
