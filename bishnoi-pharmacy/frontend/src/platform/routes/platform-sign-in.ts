import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";
import { api, ApiError, SESSION_COOKIE } from "../lib/api";
import { HOLDER_COOKIE, NOT_SHARED, SECURE_COOKIE, WHO_COOKIE } from "../lib/session-cookie";

// Back from the platform with a pass (/auth/platform?pass=...): this app's API
// checks it (app/platform_pass.py) and opens a session, kept in the same cookie
// as a sign-in with a password. Anything wrong goes back to the sign-in page,
// said in words.
export async function GET(request: NextRequest) {
  const pass = request.nextUrl.searchParams.get("pass");
  const toLogin = (message: string) => NextResponse.redirect(new URL(`/login?platform=${encodeURIComponent(message)}`, request.url));
  if (!pass) return toLogin("That sign-in link is incomplete. Sign in again.");

  // Whoever was signed in on this browser is signed out first (as with a password).
  const jar = await cookies();
  if (jar.has(SESSION_COOKIE)) await api.post("/auth/logout").catch(() => undefined);

  let session: { accessToken: string; expiresIn: number };
  try {
    session = await api.post("/auth/platform", { pass });
  } catch (error) {
    const message = error instanceof ApiError && typeof error.detail === "string" ? error.detail : "Signing in didn't work. Try again.";
    const response = toLogin(message);
    response.cookies.delete(SESSION_COOKIE);
    return response;
  }
  const response = NextResponse.redirect(new URL("/", request.url));
  response.cookies.set(SESSION_COOKIE, session.accessToken, {
    httpOnly: true,
    sameSite: "lax",
    secure: SECURE_COOKIE,
    path: "/",
    maxAge: session.expiresIn,
  });
  // Whose session this is (lib/session-cookie.ts): their Bishnoi One account. When the
  // platform's mark can't be seen from here, there's nothing to compare it with later.
  const sub = accountOf(pass);
  if (sub) {
    const seen = request.cookies.has(HOLDER_COOKIE);
    response.cookies.set(WHO_COOKIE, seen ? sub : `${sub}${NOT_SHARED}`, { httpOnly: true, sameSite: "lax", secure: SECURE_COOKIE, path: "/", maxAge: session.expiresIn });
  }
  response.headers.set("Cache-Control", "no-store");
  return response;
}

/** The Bishnoi One account a pass is for (its "sub"). Read only to label the session: the API has already checked the pass. */
function accountOf(pass: string): string | null {
  try {
    const payload = pass.split(".")[1] ?? "";
    const claims = JSON.parse(Buffer.from(payload.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf8")) as { sub?: unknown };
    return typeof claims.sub === "string" ? claims.sub.slice(0, 64) : null;
  } catch {
    return null;
  }
}
