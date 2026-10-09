import type { Metadata } from "next";
import { SIGN_IN } from "@/src/components/sign-in/copy";
import { Showcase } from "@/src/components/sign-in/showcase";
import { appUrl, THIS_APP, thisAppLabel } from "../lib/apps";
import { api } from "../lib/api";
import { LoginForm, type Demo } from "./login-form";

// Each Bishnoi One app signs in on its own page, so the tab says which one it is:
// six sign-in tabs that all read the same thing are six tabs you have to guess at.
export const metadata: Metadata = {
  title: thisAppLabel() ? `Sign in to ${thisAppLabel()}` : "Sign in",
};

// Shown only when SHOW_DEMO_ACCOUNTS=1 (development). This app's own backend
// says which demo accounts exist in its database (`uv run python -m
// app.tools.users demo` makes them), so the list only ever holds accounts that
// can sign in here, and none at all when the API isn't in development.
async function demoAccounts(): Promise<{ items: Demo[]; password: string | null }> {
  if (process.env.SHOW_DEMO_ACCOUNTS !== "1") return { items: [], password: null };
  try {
    return await api.get<{ items: Demo[]; password: string }>("/auth/demo-accounts");
  } catch {
    return { items: [], password: null };
  }
}

/**
 * Signing in with a Bishnoi One account, on the platform: the way in once the
 * platform decides who may use which application. Offered when the platform's
 * address is set for this build (NEXT_PUBLIC_BISHNOI_PLATFORM_URL).
 */
function platformSignIn(): string | null {
  if (!THIS_APP || THIS_APP === "platform" || !(process.env.NEXT_PUBLIC_BISHNOI_PLATFORM_URL ?? process.env.NEXT_PUBLIC_NABHI_PLATFORM_URL)) return null;
  const back = `${appUrl(THIS_APP)}/auth/platform`;
  return `${appUrl("platform")}/go?app=${THIS_APP}&return=${encodeURIComponent(back)}`;
}

/**
 * The sign-in page, the CRM's: the form on the left, and on a wide screen a
 * picture beside it (src/components/sign-in/showcase.tsx).
 */
export async function LoginPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  const next = typeof params.next === "string" ? params.next : "/";
  const expired = params.expired === "1";
  const denied = params.denied === "1";
  const refused = typeof params.platform === "string" ? params.platform.slice(0, 300) : null;
  const demo = await demoAccounts();
  const app = thisAppLabel();

  return (
    <main className="min-h-dvh bg-white p-3 sm:p-5">
      <div className="mx-auto grid min-h-[calc(100dvh-1.5rem)] max-w-[80rem] gap-5 sm:min-h-[calc(100dvh-2.5rem)] lg:grid-cols-[minmax(0,1fr)_minmax(0,1.08fr)]">
        <section className="flex flex-col items-center justify-center px-3 py-10 sm:px-8">
          <div className="w-full max-w-[23rem]">
            <div className="text-center">
              <h1 className="text-[2.4rem] leading-[1.1] font-semibold tracking-[-0.02em] text-[#141414] sm:text-[2.75rem]">Welcome back</h1>
              <p className="mx-auto mt-3 max-w-[20rem] text-sm leading-relaxed text-[#545454]">{SIGN_IN.lead}</p>
            </div>

            <div className="mt-8 space-y-2">
              {expired && <Notice>Your session ended. Sign in again to pick up where you left off.</Notice>}
              {denied && <Notice>The account you&apos;re signed in with doesn&apos;t work in {app ?? "this app"}. Sign in with one that does.</Notice>}
              {refused && <Notice tone="danger">{refused}</Notice>}
            </div>

            <div className="mt-4">
              <LoginForm next={next} demo={demo.items} demoPassword={demo.password} bishnoiAccount={platformSignIn()} />
            </div>

            <p className="mt-10 text-center text-sm text-[#3b3b3b]">
              New here? <span className="font-medium text-[#4f7f44]">Your administrator adds you.</span>
            </p>
          </div>
        </section>

        <Showcase />
      </div>
    </main>
  );
}

function Notice({ children, tone }: { children: React.ReactNode; tone?: "danger" }) {
  return (
    <p role={tone ? "alert" : undefined} className={`rounded-2xl px-5 py-2.5 text-sm ${tone ? "bg-danger-tint text-danger" : "bg-[#f1f7ee] text-[#3b3b3b]"}`}>
      {children}
    </p>
  );
}
