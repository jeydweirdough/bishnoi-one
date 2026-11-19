import "server-only";
import { AccountError, accountCall } from "./account";
import { moduleApiAddress } from "./backend";
import type { ModuleDef } from "./modules";

// A module's own session, from a Platform pass: only the fallback since one sign-in (stage M3, second part,
// 2026-11-18), when every module of the one backend takes the Bishnoi One account's session itself
// (src/platform/lib/api.ts). app/auth/enter uses it for a module that refuses the account token (a
// backend not yet upgraded); the Platform still decides, in the pass, who may open it.

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
