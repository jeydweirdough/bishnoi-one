import type { Metadata } from "next";
import Link from "next/link";
import { accountCall } from "@/src/platform/lib/account";
import { SignInShell } from "@/src/one/sign-in-shell";
import { LinkPasswordForm } from "@/src/one/sign-in-forms";

export const metadata: Metadata = { title: "Choose your password · Bishnoi One" };

type Search = Promise<Record<string, string | string[] | undefined>>;
type LinkInfo = { kind: "reset" | "invite"; email: string; fullName: string; company: string | null };

/** A reset (forgot password) or invitation link from an email (2026-10-30): the person chooses their password. */
export default async function LinkPasswordPage({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  const token = typeof q.invite === "string" ? q.invite : typeof q.reset === "string" ? q.reset : "";
  const info = token ? await accountCall<LinkInfo>(`/identity/password/link?token=${encodeURIComponent(token)}`).catch(() => null) : null;
  if (!info) {
    return (
      <SignInShell title="This link doesn't work any more" intro="Links work once, and only for a while. Ask for a new one.">
        <p className="mt-8 text-center text-sm">
          <Link href="/login/forgot" className="text-hema hover:underline">
            Send me a new link
          </Link>
        </p>
      </SignInShell>
    );
  }
  const invite = info.kind === "invite";
  return (
    <SignInShell
      title={invite ? `Welcome, ${info.fullName.split(" ")[0]}` : "Choose a new password"}
      intro={invite ? <>Choose the password for {info.email}{info.company ? ` at ${info.company}` : ""}. You&apos;ll sign in with it to every app.</> : <>For {info.email}. Your other sign-ins end once it&apos;s saved.</>}
    >
      <LinkPasswordForm token={token} email={info.email} invite={invite} />
    </SignInShell>
  );
}
