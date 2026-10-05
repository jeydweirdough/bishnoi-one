import type { Metadata } from "next";
import { cookies } from "next/headers";
import { COMPANY_COOKIE } from "../lib/session-cookie";
import { appUrl, THIS_APP, thisAppLabel } from "../lib/apps";
import { buttonClass } from "../ui/button";
import { APP_NAME } from "../lib/labels";
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
 * platform decides who may use which application. Shown when the platform's
 * address is set for this build (NEXT_PUBLIC_BISHNOI_PLATFORM_URL).
 */
function platformSignIn(): string | null {
  if (!THIS_APP || THIS_APP === "platform" || !(process.env.NEXT_PUBLIC_BISHNOI_PLATFORM_URL ?? process.env.NEXT_PUBLIC_NABHI_PLATFORM_URL)) return null;
  const back = `${appUrl(THIS_APP)}/auth/platform`;
  return `${appUrl("platform")}/go?app=${THIS_APP}&return=${encodeURIComponent(back)}`;
}

export async function LoginPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  const next = typeof params.next === "string" ? params.next : "/";
  const expired = params.expired === "1";
  const denied = params.denied === "1";
  const refused = typeof params.platform === "string" ? params.platform.slice(0, 300) : null;
  const bishnoiAccount = platformSignIn();
  const demo = await demoAccounts();
  const app = thisAppLabel();
  // The company last signed in to here; on this computer, the API's own default.
  const company = (await cookies()).get(COMPANY_COOKIE)?.value ?? (process.env.SHOW_DEMO_ACCOUNTS === "1" ? "getmeds" : "");

  return (
    <main className="flex min-h-dvh flex-col items-center justify-start px-4 py-10 sm:justify-center">
      <LoginForm next={next} company={company} demo={demo.items} demoPassword={demo.password}>
        {/* No company name here, and not by omission: nobody has signed in
            yet, so which company this is isn't known. One sign-in page serves
            every company on the platform. The company's own name appears the
            moment there is a person to read it from.

            Which *app* is known, though, and is said plainly. Each one signs
            in separately, and a person should see what they are entering
            rather than read it off the address bar. The shell is every app at
            once, so it has no name of its own to add. */}
        <div className="border-b-[3px] border-double border-ink pb-3">
          {app ? (
            <>
              <p className="text-stamp text-ink-3 uppercase">{APP_NAME}</p>
              <p className="text-heading leading-tight">{app}</p>
            </>
          ) : (
            <p className="text-heading">{APP_NAME}</p>
          )}
        </div>
        <h1 className="mt-6 text-title">Sign in</h1>
        {expired && <p className="mt-1 text-ink-2">Your session ended. Sign in again to pick up where you left off.</p>}
        {denied && (
          <p className="mt-1 text-ink-2">
            The account you're signed in with doesn't work in {app ?? "this app"}. Sign in with one that does.
          </p>
        )}
        {refused && (
          <p role="alert" className="mt-3 rounded-[6px] bg-danger-tint px-3 py-2 text-sm text-danger">
            {refused}
          </p>
        )}
        {bishnoiAccount && (
          <div className="mt-6">
            <a href={bishnoiAccount} className={buttonClass("primary", "md", "w-full justify-center")}>
              Sign in with your Bishnoi One account
            </a>
            <p className="mt-4 flex items-center gap-3 text-meta text-ink-3">
              <span className="h-px flex-1 bg-rule" aria-hidden />
              or with an account of {app ?? "this app"} only
              <span className="h-px flex-1 bg-rule" aria-hidden />
            </p>
          </div>
        )}
      </LoginForm>
      <p className="mt-4 text-center text-meta text-ink-3">Forgot your password? Ask your admin to reset it.</p>
    </main>
  );
}
