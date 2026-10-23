import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Showcase, type Slide } from "@/src/components/sign-in/showcase";
import { buttonClass } from "@/src/platform/ui/button";
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
    <main className="min-h-dvh bg-white p-3 sm:p-5">
      <div className="mx-auto grid min-h-[calc(100dvh-1.5rem)] max-w-[80rem] gap-5 sm:min-h-[calc(100dvh-2.5rem)] lg:grid-cols-[minmax(0,1fr)_minmax(0,1.08fr)]">
        <section className="flex flex-col px-3 pt-4 pb-6 sm:px-8">
          <Brand />
          <div className="flex flex-1 items-center justify-center py-10">
            <div className="w-full max-w-[23rem]">
              {!app || !returnTo ? (
                <Heading title="This link is incomplete" lead="Go back to the application and choose Sign in again." />
              ) : choices.length > 0 ? (
                <>
                  <AppChip appKey={key} name={name} />
                  <Heading title="Choose a company" lead={`You work for more than one. Each has its own ${name} data.`} />
                  <ul className="mt-8 space-y-2">
                    {choices.map((c) => (
                      <li key={c.slug}>
                        <a
                          href={goLink(key, returnTo, c.slug)}
                          className="flex h-14 items-center justify-between gap-3 rounded-[14px] border border-rule px-5 text-ink transition-colors hover:border-ink hover:bg-bench"
                        >
                          <span className="min-w-0 truncate font-medium">{c.name}</span>
                          <span className="flex shrink-0 items-center gap-2 text-meta text-ink-3">
                            {c.current && "Last used"}
                            <ArrowRight className="size-4" aria-hidden />
                          </span>
                        </a>
                      </li>
                    ))}
                  </ul>
                </>
              ) : refused ? (
                <>
                  {/* Not a "no access" (that one signs out and asks again): something is set up wrong or can't be reached. Said plainly, and it stays. */}
                  <AppChip appKey={key} name={name} />
                  <Heading title={`Can't open ${name}`} lead="Bishnoi One couldn't open it. The reason is below." />
                  <p role="alert" className="mt-8 rounded-[14px] bg-danger-tint px-4 py-3 text-sm text-danger">
                    {refused}
                  </p>
                  {/address/i.test(refused) && (
                    <p className="mt-3 text-sm leading-relaxed text-ink-2">
                      {name}&apos;s address on Bishnoi One doesn&apos;t match the one you came from. A Platform administrator sets each app&apos;s address in Applications (App URL).
                    </p>
                  )}
                  <a href={goLink(key, returnTo, company || undefined)} className={buttonClass("primary", "md", "mt-6 w-full justify-center")}>
                    Try again
                  </a>
                  {me && me.apps.some((x) => x.key !== key && tileOf(x.key)) && (
                    <OtherApps title="Apps you can open" apps={me.apps.filter((x) => x.key !== key).map((x) => ({ key: x.key, url: x.appUrl }))} />
                  )}
                </>
              ) : (
                <>
                  <AppChip appKey={key} name={name} />
                  <Heading
                    title="Welcome back"
                    lead={name ? `Sign in with your Bishnoi One account to continue to ${name}.` : "Sign in with your Bishnoi One account."}
                  />
                  {noApp && name && (
                    <div className="mt-6">
                      <GoNotice text={`That account doesn't include ${name}. Sign in with an account that does, or ask your company's administrator for access.`} />
                    </div>
                  )}
                  <GoForm app={key} returnTo={returnTo} company={company} />
                  {/* Came to the wrong one: open another app instead (Bishnoi One asks once, then each opens signed in). */}
                  <OtherApps
                    title={name ? `Not ${name}? Open another app` : "Open an app"}
                    apps={APP_TILES.filter((t) => t.app !== key).map((t) => ({ key: t.app, url: null }))}
                  />
                </>
              )}
              {signedIn && (
                <form action={signOutAccount} className="mt-6 text-center">
                  <input type="hidden" name="app" value={key} />
                  <input type="hidden" name="return" value={returnTo} />
                  <button type="submit" className="text-sm font-medium text-ink-2 underline-offset-4 hover:text-ink hover:underline">
                    Use another account
                  </button>
                </form>
              )}
            </div>
          </div>
          <p className="text-center text-meta text-ink-3">Forgot your password? Ask your company&apos;s administrator to reset it.</p>
        </section>

        <Showcase slides={GO_SLIDES} brand={APP_NAME} label="What one Bishnoi One account gives you" />
      </div>
    </main>
  );
}

// Beside the form: what one Bishnoi One account gives everyone who signs in
// (the Platform's own sign-in keeps its administrators' slides).
const GO_SLIDES: Slide[] = [
  { title: "One account", sub: "Every application", value: 100, chip: "Signed in", says: "One sign-in for the CRM, Inventory, Finance and more, in" },
  { title: "Your companies", sub: "Switch in one click", value: 80, chip: "Active", says: "Move between the companies you work for, in" },
  { title: "Only you", sub: "One person per browser", value: 100, chip: "Protected", says: "Your work stays yours, in" },
];

/** The brand, top left, as on every Bishnoi One screen. */
function Brand() {
  return (
    <p className="flex items-center gap-2.5">
      <img src="/brand/bishnoi-one-mark.png" alt="" width={36} height={36} className="size-9 shrink-0" />
      <span className="text-[1.0625rem] font-semibold tracking-[-0.01em] text-ink">{APP_NAME}</span>
    </p>
  );
}

/** The page's heading and its line, centred, as on each app's own sign-in. */
function Heading({ title, lead }: { title: string; lead: string }) {
  return (
    <div className="text-center">
      <h1 className="text-[2.4rem] leading-[1.1] font-semibold tracking-[-0.02em] text-ink sm:text-[2.75rem]">{title}</h1>
      <p className="mx-auto mt-3 max-w-[21rem] text-sm leading-relaxed text-ink-2">{lead}</p>
    </div>
  );
}

/** Which application this sign-in opens: its tile and name, above the heading. */
function AppChip({ appKey, name }: { appKey: string; name: string | null }) {
  const tile = tileOf(appKey);
  if (!tile || !name) return null;
  const Icon = tile.icon;
  return (
    <p className="mb-6 flex justify-center">
      <span className="inline-flex h-9 items-center gap-2 rounded-full border border-rule bg-white pr-3.5 pl-1.5 text-meta font-medium text-ink-2">
        <span className="grid size-6 place-items-center rounded-full" style={{ background: tile.tint, color: tile.ink }}>
          <Icon className="size-3.5" aria-hidden />
        </span>
        {name}
      </span>
    </p>
  );
}

/** Other apps as small pills, each through this page again for that app (and so signed in, once they are). */
function OtherApps({ title, apps }: { title: string; apps: { key: string; url: string | null }[] }) {
  const tiles = apps.map((x) => ({ ...x, tile: tileOf(x.key) })).filter((x) => x.tile);
  if (tiles.length === 0) return null;
  return (
    <div className="mt-10">
      <p className="text-center text-meta text-ink-3">{title}</p>
      <ul className="mt-3 flex flex-wrap justify-center gap-2">
        {tiles.map(({ key, url, tile }) => {
          const Icon = tile!.icon;
          const address = (url || appUrl(tile!.app as AppName)).replace(/\/$/, "");
          const href = tile!.app === "platform" ? address : goLink(key, `${address}/auth/platform`);
          return (
            <li key={key}>
              <a
                href={href}
                className="inline-flex h-9 items-center gap-2 rounded-full border border-rule bg-white pr-3.5 pl-1.5 text-meta font-medium text-ink-2 transition-colors hover:border-ink hover:text-ink"
              >
                <span className="grid size-6 place-items-center rounded-full" style={{ background: tile!.tint, color: tile!.ink }}>
                  <Icon className="size-3.5" aria-hidden />
                </span>
                {appLabel(tile!.app)}
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
