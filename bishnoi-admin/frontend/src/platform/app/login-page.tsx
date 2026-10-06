import type { Metadata } from "next";
import Image from "next/image";
import logo from "@/src/components/assets/logo.png";
import { appUrl, THIS_APP, thisAppLabel } from "../lib/apps";
import { buttonClass } from "../ui/button";
import { APP_NAME } from "../lib/labels";
import { api } from "../lib/api";
import { LoginForm, type Demo } from "./login-form";

// Each Bishnoi One app signs in on its own page, so the tab says which one it is:
// six sign-in tabs that all read the same thing are six tabs you have to guess at.
export const metadata: Metadata = {
  title: { absolute: thisAppLabel() ? `Sign in to ${APP_NAME} ${thisAppLabel()}` : `Sign in to ${APP_NAME}` },
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

// The panel's circles: soft white and navy over the blue, so they read as
// light and shade on it rather than as more blue.
const CIRCLES: { className: string; background: string }[] = [
  { className: "-top-[16vmin] left-[34%] size-[34vmin]", background: "rgb(255 255 255 / 0.18)" },
  { className: "-top-[10vmin] -right-[8vmin] size-[30vmin]", background: "linear-gradient(200deg, #1379b8 0%, #0c3a68 80%)" },
  { className: "top-[48%] -left-[14vmin] size-[32vmin]", background: "linear-gradient(160deg, rgb(255 255 255 / 0.35) 0%, rgb(255 255 255 / 0.08) 100%)" },
  { className: "-bottom-[6vmin] -right-[4vmin] size-[16vmin]", background: "rgb(255 255 255 / 0.2)" },
  { className: "bottom-[7vmin] right-[8vmin] size-[6vmin]", background: "#0c3a68" },
];

export async function LoginPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  const next = typeof params.next === "string" ? params.next : "/";
  const expired = params.expired === "1";
  const denied = params.denied === "1";
  const refused = typeof params.platform === "string" ? params.platform.slice(0, 300) : null;
  const bishnoiAccount = platformSignIn();
  const demo = await demoAccounts();
  const app = thisAppLabel();
  // No company name here, and not by omission: nobody has signed in yet, so
  // which company this is isn't known. Which *app* is known, and is said
  // plainly: each one signs in separately.
  const name = app ? `${APP_NAME} ${app}` : APP_NAME;
  const notice = expired
    ? "Your session ended. Log in again to pick up where you left off."
    : denied
      ? `The account you're signed in with doesn't work in ${name}. Log in with one that does.`
      : undefined;

  return (
    <main className="min-h-dvh bg-sheet">
      <LoginForm
        next={next}
        demo={demo.items}
        demoPassword={demo.password}
        notice={notice}
        before={
          <>
            {refused && (
              <p role="alert" className="mt-4 rounded-[14px] bg-danger-tint px-3 py-2 text-sm text-danger">
                {refused}
              </p>
            )}
            {bishnoiAccount && (
              <div className="mt-6">
                <a href={bishnoiAccount} className={buttonClass("primary", "md", "w-full justify-center")}>
                  Log in with your Bishnoi One account
                </a>
                <p className="mt-4 flex items-center gap-3 text-meta text-ink-3">
                  <span className="h-px flex-1 bg-rule" aria-hidden />
                  or with an account of {app ?? "this app"} only
                  <span className="h-px flex-1 bg-rule" aria-hidden />
                </p>
              </div>
            )}
          </>
        }
        brand={
          <span className="flex flex-col items-center gap-3">
            <Image src={logo} alt="" aria-hidden className="h-14 w-auto" priority />
            <span className="text-lg font-bold tracking-tight text-[#0c3a68]">{name}</span>
          </span>
        }
        panel={
          <>
            {CIRCLES.map((c) => (
              <span key={c.className} aria-hidden className={`absolute rounded-full ${c.className}`} style={{ background: c.background }} />
            ))}
            <div className="relative flex flex-col items-center gap-5">
              <Image src={logo} alt="" aria-hidden className="h-[clamp(7rem,16vmin,10rem)] w-auto" priority />
              <p className="text-center text-[clamp(1.375rem,2vw,1.75rem)] leading-tight font-semibold tracking-tight text-white">{name}</p>
            </div>
          </>
        }
      />
    </main>
  );
}
