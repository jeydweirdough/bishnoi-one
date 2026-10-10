import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { appLabel, appOf } from "@/src/platform/lib/apps";
import { APP_NAME } from "@/src/platform/lib/labels";
import { AccountError, accountCall, accountToken, goLink, withPass, type AccountMe } from "./account";
import { signOutAccount } from "./actions";
import { GoForm } from "./go-form";

export const metadata: Metadata = { title: "Sign in with your Bishnoi One account" };

type Search = Promise<Record<string, string | string[] | undefined>>;

/**
 * One sign-in for every Bishnoi One application. An application's sign-in page
 * sends people here (?app=crm&return=<its address>/auth/platform); signed in,
 * they go back with a pass for that application, if their account has it.
 *
 * Someone who works for more than one company picks which, each time (or the
 * link names it: &company=getmeds). So an application's Switch company only
 * has to send them here again.
 */
export async function GoPage({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  const key = typeof q.app === "string" ? q.app : "";
  const returnTo = typeof q.return === "string" ? q.return : "";
  const company = typeof q.company === "string" ? q.company : "";
  const app = appOf(key);
  const name = app ? appLabel(app) : null;

  let refused: string | null = null;
  let choices: AccountMe["companies"] = [];
  const token = await accountToken();
  if (token && app && returnTo) {
    let target: string | null = null;
    try {
      if (!company) {
        const me = await accountCall<AccountMe>("/identity/me", undefined, token);
        if (me.companies.length > 1) choices = me.companies;
      }
      if (choices.length === 0) {
        const made = await accountCall<{ pass: string; returnTo: string }>("/identity/pass", { app: key, returnTo, ...(company ? { company } : {}) }, token);
        target = withPass(made.returnTo, made.pass);
      }
    } catch (e) {
      // 401: that sign-in has ended; ask again. Anything else is said as it is.
      if (!(e instanceof AccountError && e.status === 401)) refused = e instanceof Error ? e.message : "Opening the application didn't work.";
      choices = [];
    }
    if (target) redirect(target);
  }
  const signedIn = Boolean(token) && (refused !== null || choices.length > 0);

  return (
    <main className="flex min-h-dvh flex-col items-center justify-start px-4 py-10 sm:justify-center">
      <div className="w-full max-w-md rounded-[18px] bg-sheet px-6 pt-6 pb-7 shadow-sheet sm:px-8">
        <div className="border-b-[3px] border-double border-ink pb-3">
          <p className="text-stamp text-ink-3 uppercase">{APP_NAME}</p>
          <p className="text-heading leading-tight">{name ? `Opening ${name}` : "Your Bishnoi One account"}</p>
        </div>
        {!app || !returnTo ? (
          <p className="mt-6 text-ink-2">This sign-in link is incomplete. Go back to the application and choose Sign in with your Bishnoi One account again.</p>
        ) : choices.length > 0 ? (
          <>
            <h1 className="mt-6 text-title">Which company?</h1>
            <p className="mt-1 text-ink-2">You work for more than one. Each has its own {name} data.</p>
            <ul className="mt-5 space-y-2">
              {choices.map((c) => (
                <li key={c.slug}>
                  <a
                    href={goLink(key, returnTo, c.slug)}
                    className="flex items-center justify-between rounded-[18px] border border-rule-strong px-4 py-3 text-ink hover:border-hema"
                  >
                    <span className="font-medium">{c.name}</span>
                    {c.current && <span className="text-meta text-ink-3">Last used</span>}
                  </a>
                </li>
              ))}
            </ul>
          </>
        ) : refused ? (
          <>
            <h1 className="mt-6 text-title">Can't open {name}</h1>
            <p role="alert" className="mt-2 rounded-[14px] bg-danger-tint px-3 py-2 text-sm text-danger">
              {refused}
            </p>
          </>
        ) : (
          <>
            <h1 className="mt-6 text-title">Sign in</h1>
            <p className="mt-1 text-ink-2">One Bishnoi One account for every application your company gives you.</p>
            <GoForm app={key} returnTo={returnTo} company={company} />
          </>
        )}
        {signedIn && (
          <form action={signOutAccount} className="mt-5">
            <input type="hidden" name="app" value={key} />
            <input type="hidden" name="return" value={returnTo} />
            <button type="submit" className="text-sm font-medium text-hema hover:underline">
              Sign in with another account
            </button>
          </form>
        )}
      </div>
      <p className="mt-4 text-center text-meta text-ink-3">Forgot your password? Ask your company&apos;s administrator to reset it.</p>
    </main>
  );
}
