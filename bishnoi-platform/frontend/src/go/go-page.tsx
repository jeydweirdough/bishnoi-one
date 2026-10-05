import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { appLabel, appOf } from "@/src/platform/lib/apps";
import { APP_NAME } from "@/src/platform/lib/labels";
import { AccountError, accountCall, accountToken, withPass } from "./account";
import { signOutAccount } from "./actions";
import { GoForm } from "./go-form";

export const metadata: Metadata = { title: "Sign in with your Bishnoi One account" };

type Search = Promise<Record<string, string | string[] | undefined>>;

/**
 * One sign-in for every Bishnoi One application. An application's sign-in page
 * sends people here (?app=crm&return=<its address>/auth/platform); signed in,
 * they go back with a pass for that application, if their account has it.
 */
export async function GoPage({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  const key = typeof q.app === "string" ? q.app : "";
  const returnTo = typeof q.return === "string" ? q.return : "";
  const app = appOf(key);
  const name = app ? appLabel(app) : null;

  let refused: string | null = null;
  const token = await accountToken();
  if (token && app && returnTo) {
    let target: string | null = null;
    try {
      const made = await accountCall<{ pass: string; returnTo: string }>("/identity/pass", { app: key, returnTo }, token);
      target = withPass(made.returnTo, made.pass);
    } catch (e) {
      // 401: that sign-in has ended; ask again. Anything else is said as it is.
      if (!(e instanceof AccountError && e.status === 401)) refused = e instanceof Error ? e.message : "Opening the application didn't work.";
    }
    if (target) redirect(target);
  }
  const signedIn = Boolean(token) && refused !== null;

  return (
    <main className="flex min-h-dvh flex-col items-center justify-start px-4 py-10 sm:justify-center">
      <div className="w-full max-w-md rounded-[3px] bg-sheet px-6 pt-6 pb-7 shadow-sheet sm:px-8">
        <div className="border-b-[3px] border-double border-ink pb-3">
          <p className="text-stamp text-ink-3 uppercase">{APP_NAME}</p>
          <p className="text-heading leading-tight">{name ? `Opening ${name}` : "Your Bishnoi One account"}</p>
        </div>
        {!app || !returnTo ? (
          <p className="mt-6 text-ink-2">This sign-in link is incomplete. Go back to the application and choose Sign in with your Bishnoi One account again.</p>
        ) : refused ? (
          <>
            <h1 className="mt-6 text-title">Can't open {name}</h1>
            <p role="alert" className="mt-2 rounded-[3px] bg-danger-tint px-3 py-2 text-sm text-danger">
              {refused}
            </p>
            {signedIn && (
              <form action={signOutAccount} className="mt-5">
                <input type="hidden" name="app" value={key} />
                <input type="hidden" name="return" value={returnTo} />
                <button type="submit" className="text-sm font-medium text-hema hover:underline">
                  Sign in with another account
                </button>
              </form>
            )}
          </>
        ) : (
          <>
            <h1 className="mt-6 text-title">Sign in</h1>
            <p className="mt-1 text-ink-2">One Bishnoi One account for every application your company gives you.</p>
            <GoForm app={key} returnTo={returnTo} />
          </>
        )}
      </div>
      <p className="mt-4 text-center text-meta text-ink-3">Forgot your password? Ask your company&apos;s administrator to reset it.</p>
    </main>
  );
}
