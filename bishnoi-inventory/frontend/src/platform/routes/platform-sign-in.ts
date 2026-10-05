import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";
import { api, ApiError, SESSION_COOKIE } from "../lib/api";
import { COMPANY_COOKIE, companyOfToken } from "../lib/session-cookie";

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
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: session.expiresIn,
  });
  // The company the pass was for, for the sign-in page next time.
  const company = companyOfToken(session.accessToken);
  if (company) {
    response.cookies.set(COMPANY_COOKIE, company, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 400 * 24 * 3600 });
  }
  response.headers.set("Cache-Control", "no-store");
  return response;
}
