import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Showcase, type Slide } from "@/src/components/sign-in/showcase";
import { accountCall, accountToken, type Account } from "@/src/platform/lib/account";
import { APP_NAME } from "@/src/platform/lib/labels";
import { Brand } from "@/src/one/brand";
import { LoginForm } from "@/src/one/login-form";

export const metadata: Metadata = { title: "Sign in to Bishnoi One" };

type Search = Promise<Record<string, string | string[] | undefined>>;

// Beside the form: what one Bishnoi One account gives everyone who signs in.
const SLIDES: Slide[] = [
  { title: "One account", sub: "Every module", value: 100, chip: "Signed in", says: "One sign-in for the CRM, Inventory, Finance and more, in" },
  { title: "Your companies", sub: "Switch in one click", value: 80, chip: "Active", says: "Move between the companies you work for, in" },
  { title: "Only you", sub: "One person per browser", value: 100, chip: "Protected", says: "Your work stays yours, in" },
];

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

  return (
    <main className="min-h-dvh bg-white p-3 sm:p-5">
      <div className="mx-auto grid min-h-[calc(100dvh-1.5rem)] max-w-[80rem] gap-5 sm:min-h-[calc(100dvh-2.5rem)] lg:grid-cols-[minmax(0,1fr)_minmax(0,1.08fr)]">
        <section className="flex flex-col px-3 pt-4 pb-6 sm:px-8">
          <Brand href="/login" />
          <div className="flex flex-1 items-center justify-center py-10">
            <div className="w-full max-w-[23rem]">
              <div className="text-center">
                <h1 className="text-[2.4rem] leading-[1.1] font-semibold tracking-[-0.02em] text-ink sm:text-[2.75rem]">Welcome back</h1>
                <p className="mx-auto mt-3 max-w-[21rem] text-sm leading-relaxed text-ink-2">Sign in with your Bishnoi One account. One account opens every module your company gives you.</p>
              </div>
              {expired && <p className="mt-6 rounded-lg bg-[#f1f7ee] px-4 py-2.5 text-center text-sm text-ink-2">Your session ended. Sign in again to pick up where you left off.</p>}
              <LoginForm next={next} />
            </div>
          </div>
          <p className="text-center text-meta text-ink-3">Forgot your password? Ask your company&apos;s administrator to reset it.</p>
        </section>
        <Showcase slides={SLIDES} brand={APP_NAME} label="What one Bishnoi One account gives you" />
      </div>
    </main>
  );
}
