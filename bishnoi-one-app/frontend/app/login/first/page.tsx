import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { accountCall, accountToken, type Account } from "@/src/platform/lib/account";
import { FirstSteps } from "@/src/one/first-steps";

export const metadata: Metadata = { title: "Before you start · Bishnoi One" };

type Search = Promise<Record<string, string | string[] | undefined>>;

/**
 * Before anything else (2026-10-30): a password someone handed over is changed for one's own, and
 * administrators set up two-step sign-in where it's required. The one app sends them here until done.
 * Everyone else without two-step sign-in comes here once per sign-in, and may skip it.
 */
export default async function FirstSignInPage({ searchParams }: { searchParams: Search }) {
  const q = await searchParams;
  const asked = typeof q.next === "string" ? q.next : "/";
  const next = asked.startsWith("/") && !asked.startsWith("//") && !asked.startsWith("/login") ? asked : "/";
  const token = await accountToken();
  const me = token ? await accountCall<Account>("/identity/me", undefined, token).catch(() => null) : null;
  if (!me) redirect("/login");
  const password = Boolean(me.mustChangePassword);
  const twoStep = Boolean(me.twoStep?.needed);
  // Just after signing in, whoever hasn't two-step sign-in is offered it (2026-11-01); they may skip it.
  const offer = q.offer === "1" && Boolean(me.twoStep?.suggested);
  if (!password && !twoStep && !offer) redirect(next);
  return <FirstSteps password={password} twoStep={twoStep} offer={offer} next={next} />;
}
