import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";
import { ACCOUNT_COOKIE, accountCall, goLink, HOLDER_COOKIE, HOLDER_DOMAIN } from "@/src/go/account";

// Signing out of an application ends the Bishnoi One sign-in too (decided
// 2026-10-21): every application now signs in through it, so leaving it open
// would sign the person straight back in. The application ends its own
// session, then sends them here (?app=crm&return=<its address>/auth/platform);
// this ends theirs, and shows the Bishnoi One sign-in for that application.
export async function GET(request: NextRequest) {
  const app = request.nextUrl.searchParams.get("app") ?? "";
  const returnTo = request.nextUrl.searchParams.get("return") ?? "";
  const token = (await cookies()).get(ACCOUNT_COOKIE)?.value;
  if (token) await accountCall("/identity/logout", {}, token).catch(() => undefined);
  // ?notice=noapp: they were signed out because the account can't open this app; the sign-in says so.
  const notice = request.nextUrl.searchParams.get("notice") === "noapp" ? "&notice=noapp" : "";
  const response = NextResponse.redirect(new URL(app && returnTo ? `${goLink(app, returnTo)}${notice}` : "/go", request.url));
  response.cookies.delete(ACCOUNT_COOKIE);
  // Nobody is signed in here now: every app's session from Bishnoi One ends at its next page.
  response.cookies.set(HOLDER_COOKIE, "", { path: "/", domain: HOLDER_DOMAIN, maxAge: 0 });
  response.headers.set("Cache-Control", "no-store");
  return response;
}
