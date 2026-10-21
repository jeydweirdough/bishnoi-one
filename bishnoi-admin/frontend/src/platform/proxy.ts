import { NextResponse, type NextRequest } from "next/server";
import { HOLDER_COOKIE, NOT_SHARED, SESSION_COOKIE, WHO_COOKIE } from "./lib/session-cookie";

// A quick first gate: no session cookie, no pages. The API still checks the
// token on every request; this only saves a round trip to a page that would
// bounce anyway.
//
// And one person per browser (lib/session-cookie.ts): a session that isn't the
// person signed in to Bishnoi One on this browser now is ended here, and they
// go to sign in, which opens the app as whoever is signed in now.
export async function proxy(request: NextRequest) {
  const session = request.cookies.get(SESSION_COOKIE)?.value;
  if (session && !someoneElse(request)) return NextResponse.next();
  const login = new URL("/login", request.url);
  const next = request.nextUrl.pathname + request.nextUrl.search;
  if (next !== "/") login.searchParams.set("next", next);
  const response = NextResponse.redirect(login);
  if (session) {
    // Ended in the API too, so the token can't be used again; the cookies go either way.
    const api = (process.env.API_URL ?? "").replace(/\/$/, "");
    if (api) await fetch(`${api}/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${session}` }, signal: AbortSignal.timeout(3000) }).catch(() => undefined);
    response.cookies.delete(SESSION_COOKIE);
    response.cookies.delete(WHO_COOKIE);
  }
  return response;
}

/** Whether this browser's session belongs to someone other than the person signed in to Bishnoi One here. */
function someoneElse(request: NextRequest): boolean {
  const holder = request.cookies.get(HOLDER_COOKIE)?.value;
  const who = request.cookies.get(WHO_COOKIE)?.value;
  if (who?.endsWith(NOT_SHARED)) return false;
  // Signed in with this app's own password (local:<who held Bishnoi One then>):
  // it ends when someone else signs in to Bishnoi One after it, not before.
  if (who?.startsWith("local:")) return (holder ?? "") !== who.slice("local:".length);
  // Someone is signed in to Bishnoi One: this session must be theirs.
  if (holder) return who !== holder;
  // Nobody is (they signed out of Bishnoi One): a session opened through it ends with it.
  return Boolean(who);
}

export const config = {
  matcher: ["/((?!login|_next/static|_next/image|favicon.ico).*)"],
};
