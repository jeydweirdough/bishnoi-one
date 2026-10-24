import { NextResponse, type NextRequest } from "next/server";
import { isPublicPath, moduleOfPath } from "./lib/modules";
import { ACCOUNT_COOKIE, HERE_COOKIE, MODULE_HEADER, cookieOptions, moduleCookie } from "./lib/session-cookie";

// The first gate for every page of the one app (decided 2026-10-23):
//  - no Bishnoi One account here: sign in first (the API checks every request
//    anyway; this only saves a page that would bounce);
//  - a page of a module whose screens are here: the request is marked with
//    that module (MODULE_HEADER, from the path only, so the browser can't pick
//    another), and the module's session is opened on first use (app/auth/enter).
export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const next = pathname + search;
  const here = moduleOfPath(pathname);
  const headers = new Headers(request.headers);
  headers.delete(MODULE_HEADER);
  // A module's public page (a customer's order link): anyone, signed in or not, still talking to that module's API.
  if (here && here.status === "live" && isPublicPath(here, pathname)) {
    headers.set(MODULE_HEADER, here.key);
    return NextResponse.next({ request: { headers } });
  }
  if (!request.cookies.get(ACCOUNT_COOKIE)?.value) {
    const login = new URL("/login", request.url);
    if (next !== "/") login.searchParams.set("next", next);
    return NextResponse.redirect(login);
  }

  if (!here || here.status !== "live") return NextResponse.next({ request: { headers } });
  // The Admin Console works on the account itself: marked as its module (its API is the Platform's), no session to open.
  if (here.accountOnly) {
    headers.set(MODULE_HEADER, here.key);
    return NextResponse.next({ request: { headers } });
  }

  if (!request.cookies.get(moduleCookie(here.key))?.value) {
    const enter = new URL(`/auth/enter/${here.key}`, request.url);
    enter.searchParams.set("next", next);
    return NextResponse.redirect(enter);
  }
  headers.set(MODULE_HEADER, here.key);
  const response = NextResponse.next({ request: { headers } });
  // Where they are, so a module session that ends mid-way reopens and brings them back (app/auth/renew).
  if (request.method === "GET") response.cookies.set(HERE_COOKIE, `${here.key}|${next}`.slice(0, 1000), cookieOptions(8 * 3600));
  return response;
}
