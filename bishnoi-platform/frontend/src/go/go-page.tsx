import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { loadAddresses } from "@/src/platform/lib/addresses";
import { APP_TILES, tileOf } from "@/src/platform/lib/app-tiles";
import { appLabel, appOf, appUrl, type AppName } from "@/src/platform/lib/apps";
import { APP_NAME } from "@/src/platform/lib/labels";
import { AccountError, accountCall, accountToken, goLink, withPass, type AccountMe } from "./account";
import { signOutAccount } from "./actions";
import { GoForm } from "./go-form";
import { GoNotice } from "./go-notice";

export const metadata: Metadata = { title: "Sign in with your Bishnoi One account" };

type Search = Promise<Record<string, string | string[] | undefined>>;

const EVERY_APP: AppName[] = ["exec", "crm", "finance", "inventory", "regulatory", "inlicensing", "pharmacy", "platform"];

/**
 * Where to send someone back to with a refusal (the app launcher's &from=):
 * only a page of one of the Bishnoi One apps, so the link can't be used to
 * bounce people to another site. Null for anything else.
 */
async function backTo(from: string): Promise<string | null> {
  await loadAddresses();
  const ours = new Set(EVERY_APP.map((a) => { try { return new URL(appUrl(a)).origin; } catch { return ""; } }));
  try {
    const url = new URL(from);
    if (!["http:", "https:"].includes(url.protocol) || !ours.has(url.origin)) return null;
    url.searchParams.delete("appNotice");
    return url.toString();
  } catch {
    return null;
  }
}

/**
 * One sign-in for every Bishnoi One application. An application's sign-in page
 * sends people here (?app=crm&return=<its address>/auth/platform); signed in,
 * they go back with a pass for that application, if their account has it.
 *
 * Someone who works for more than one company goes to the one they last used
 * (or the link names it: &company=getmeds); an application's Switch company
 * sends them here with &choose=1, which lists their companies to pick from.
 */
export async function GoPage({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  const key = typeof q.app === "string" ? q.app : "";
  const returnTo = typeof q.return === "string" ? q.return : "";
  const company = typeof q.company === "string" ? q.company : "";
  // Switch company asks (&choose=1); every other way in goes to the company they last used.
  const choose = q.choose === "1";
  // The page the app launcher was opened on: a refusal goes back there as an alert.
  const from = typeof q.from === "string" ? q.from : "";
  // Back at the sign-in because the last account couldn't open this app (a code, not text, so a link can't put words here).
  const noApp = q.notice === "noapp";
  const app = appOf(key);
  const name = app ? appLabel(app) : null;

  let refused: string | null = null;
  let refusedStatus = 0;
  let choices: AccountMe["companies"] = [];
  const token = await accountToken();
  await loadAddresses();
  // Who they are, when signed in: their companies, and the apps they may open (listed on this page).
  const me = token ? await accountCall<AccountMe>("/identity/me", undefined, token).catch(() => null) : null;
  if (token && app && returnTo) {
    let target: string | null = null;
    try {
      if (!company && me) {
        if (me.companies.length > 1 && (choose || !me.companies.some((c) => c.current))) choices = me.companies;
      }
      if (choices.length === 0) {
        const made = await accountCall<{ pass: string; returnTo: string }>("/identity/pass", { app: key, returnTo, ...(company ? { company } : {}) }, token);
        target = withPass(made.returnTo, made.pass);
      }
    } catch (e) {
      // 401: that sign-in has ended; ask again. Anything else is said as it is.
      if (!(e instanceof AccountError && e.status === 401)) refused = e instanceof Error ? e.message : "Opening the application didn't work.";
      refusedStatus = e instanceof AccountError ? e.status : 0;
      choices = [];
    }
    // Through /go/hold, which marks this browser with who is signed in (one person per browser).
    if (target) redirect(`/go/hold?to=${encodeURIComponent(target)}`);
    if (refused && from) {
      const back = await backTo(from);
      if (back) redirect(`${back}${back.includes("?") ? "&" : "?"}appNotice=${encodeURIComponent(refused.slice(0, 300))}`);
    }
    // Opened straight (not from an app's launcher) with an account that can't open it:
    // that account is signed out here, and the sign-in shows why, for the right one.
    if (refused && refusedStatus === 403) redirect(`/go/signout?app=${encodeURIComponent(key)}&return=${encodeURIComponent(returnTo)}&notice=noapp`);
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
            <h1 className="mt-6 text-title">Select a company</h1>
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
            {/* The "no" is an alert over the page; the page is where to go instead. */}
            <GoNotice text={refused} />
            <h1 className="mt-6 text-title">Choose an app</h1>
            <p className="mt-1 text-ink-2">
              Signed in as <span className="font-medium text-ink">{me?.email ?? "your Bishnoi One account"}</span>
              {me?.company ? ` at ${me.company.name}` : ""}.
            </p>
            {me && me.apps.some((x) => x.key !== key && tileOf(x.key)) ? (
              <OtherApps title="Apps you can open" apps={me.apps.filter((x) => x.key !== key).map((x) => ({ key: x.key, url: x.appUrl }))} />
            ) : (
              <p className="mt-4 rounded-[14px] bg-bench px-3 py-2.5 text-sm text-ink-2">No apps are given to your account yet. Ask your company&apos;s administrator for access.</p>
            )}
          </>
        ) : (
          <>
            {noApp && name && <GoNotice text={`That account doesn't include ${name}. Sign in with an account that does, or ask your company's administrator for access.`} />}
            <h1 className="mt-6 text-title">Sign in</h1>
            <p className="mt-1 text-ink-2">One Bishnoi One account for every application your company gives you.</p>
            <GoForm app={key} returnTo={returnTo} company={company} />
            {/* Came to the wrong one: pick the app to open after signing in. */}
            <OtherApps title="Or open another app" apps={APP_TILES.filter((t) => t.app !== key).map((t) => ({ key: t.app, url: null }))} />
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

/** Other apps as small tiles, each through this page again for that app (and so signed in, once they are). */
function OtherApps({ title, apps }: { title: string; apps: { key: string; url: string | null }[] }) {
  const tiles = apps.map((x) => ({ ...x, tile: tileOf(x.key) })).filter((x) => x.tile);
  if (tiles.length === 0) return null;
  return (
    <div className="mt-6 border-t border-rule pt-4">
      <p className="text-meta font-semibold text-ink-3">{title}</p>
      <ul className="mt-2.5 grid grid-cols-3 gap-1.5">
        {tiles.map(({ key, url, tile }) => {
          const Icon = tile!.icon;
          const address = (url || appUrl(tile!.app as AppName)).replace(/\/$/, "");
          const href = tile!.app === "platform" ? address : goLink(key, `${address}/auth/platform`);
          return (
            <li key={key}>
              <a href={href} className="flex flex-col items-center rounded-xl px-1 py-2 text-center transition-colors hover:bg-bench">
                <span className="grid size-10 place-items-center rounded-xl" style={{ background: tile!.tint, color: tile!.ink }}>
                  <Icon className="size-5" aria-hidden />
                </span>
                <span className="mt-1 text-meta font-semibold text-ink">{appLabel(tile!.app)}</span>
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
