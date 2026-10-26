import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { accountCall } from "@/src/platform/lib/account";
import { Brand } from "@/src/one/brand";
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
    <main className="min-h-dvh bg-white p-3 sm:p-5">
      <section className="mx-auto flex min-h-[calc(100dvh-1.5rem)] max-w-[40rem] flex-col px-3 pt-4 pb-6 sm:px-8">
        <Brand href="/setup" />
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-[23rem]">
            <div className="text-center">
              <h1 className="text-[2.4rem] leading-[1.1] font-semibold tracking-[-0.02em] text-ink sm:text-[2.75rem]">Set up Bishnoi One</h1>
              <p className="mx-auto mt-3 max-w-[21rem] text-sm leading-relaxed text-ink-2">Your company and its first administrator. You can add everyone else afterwards.</p>
            </div>
            <SetupForm />
          </div>
        </div>
      </section>
    </main>
  );
}
