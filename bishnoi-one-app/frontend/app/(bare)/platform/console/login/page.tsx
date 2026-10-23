import type { Metadata } from "next";
import { Brand } from "@/src/one/brand";
import { consoleSignIn } from "@/src/one/console-actions";
import { LoginForm } from "@/src/one/login-form";

export const metadata: Metadata = { title: "Sign in to the Platform console" };

type Search = Promise<Record<string, string | string[] | undefined>>;

/** The Platform console's sign-in: Bishnoi One's own staff, with their staff account (not a company's). */
export default async function ConsoleLoginPage({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  const next = typeof q.next === "string" && q.next.startsWith("/platform/console") ? q.next : "/platform/console";
  return (
    <main className="min-h-dvh bg-white p-3 sm:p-5">
      <section className="mx-auto flex min-h-[calc(100dvh-1.5rem)] max-w-[30rem] flex-col px-3 pt-4 pb-6 sm:px-8">
        <Brand href="/" />
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-[23rem]">
            <div className="text-center">
              <h1 className="text-[2.2rem] leading-[1.1] font-semibold tracking-[-0.02em] text-ink">Platform console</h1>
              <p className="mx-auto mt-3 max-w-[21rem] text-sm leading-relaxed text-ink-2">
                For Bishnoi One&apos;s staff: companies, applications and support. Sign in with your staff account.
              </p>
            </div>
            <LoginForm next={next} signInWith={consoleSignIn} />
          </div>
        </div>
        <p className="text-center text-meta text-ink-3">A company&apos;s people sign in on the main sign-in page.</p>
      </section>
    </main>
  );
}
