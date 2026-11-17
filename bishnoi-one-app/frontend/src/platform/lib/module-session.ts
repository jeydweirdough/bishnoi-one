import "server-only";
import { cookies } from "next/headers";
import { AccountError, accountCall, type Account } from "./account";
import { moduleApiAddress } from "./backend";
import { MODULES, type ModuleDef } from "./modules";
import { COMPANY_COOKIE, companyOfToken, cookieOptions, moduleCookie } from "./session-cookie";

// One sign-in (stage M3, 2026-11-18): signing in to Bishnoi One opens every part at once, so moving
// between the groups of the one menu never stops to open anything. The Platform still hands a pass
// for each part it lets this person open (it decides who may), and each part turns it into its
// session; app/auth/enter is only the fallback, for a part whose session ran out.

/** `signedOut`: the Bishnoi One sign-in itself has ended (sign in again); otherwise only this part refused. */
export type Opened = { ok: true; token: string; expiresIn: number } | { ok: false; signedOut: boolean; message: string };

/** The Platform's pass for one part, turned into that part's session. */
export async function openModuleSession(m: ModuleDef, account: string, origin: string, address: string | null): Promise<Opened> {
  let pass: string;
  try {
    pass = (await accountCall<{ pass: string }>("/identity/pass", { app: m.appKey, returnTo: `${origin}/auth/platform` }, account, address)).pass;
  } catch (error) {
    return { ok: false, signedOut: error instanceof AccountError && error.status === 401, message: error instanceof Error ? error.message : `${m.label} couldn't be opened.` };
  }
  try {
    const response = await fetch(`${moduleApiAddress(m)}/auth/platform`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(address ? { "X-Forwarded-For": address } : {}) },
      body: JSON.stringify({ pass }),
      cache: "no-store",
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) return { ok: false, signedOut: false, message: typeof data?.detail === "string" ? data.detail : `${m.label} didn't open (error ${response.status}).` };
    return { ok: true, token: data.accessToken, expiresIn: data.expiresIn };
  } catch {
    return { ok: false, signedOut: false, message: `${m.label} can't be reached just now. Try again in a minute.` };
  }
}

/** The parts this person may open: what the Platform gives them, built and with a session of its own. */
export function partsOf(me: Account): ModuleDef[] {
  const given = new Set(me.apps.map((a) => a.key));
  return MODULES.filter((m) => m.status === "live" && !m.accountOnly && given.has(m.appKey));
}

/**
 * Every part's session, opened together right after signing in (or moving to another company). A part
 * that won't open is left out quietly: its first page opens it the old way (app/auth/enter) and says why.
 */
export async function openEveryPart(account: string, origin: string, address: string | null): Promise<void> {
  let me: Account;
  try {
    me = await accountCall<Account>("/identity/me", undefined, account);
  } catch {
    return;
  }
  const parts = partsOf(me);
  const opened = await Promise.all(parts.map((m) => openModuleSession(m, account, origin, address)));
  const jar = await cookies();
  opened.forEach((o, i) => {
    if (!o.ok) return;
    jar.set(moduleCookie(parts[i].key), o.token, cookieOptions(o.expiresIn));
    const company = companyOfToken(o.token);
    if (company) jar.set(COMPANY_COOKIE, company, cookieOptions(400 * 24 * 3600));
  });
}
