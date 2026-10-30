import { NextResponse, type NextRequest } from "next/server";
import { borrowedOf, isPublicPath, moduleOfPath, moduleByKey } from "./lib/modules";
import { ACCOUNT_COOKIE, FRAME_HEADER, HERE_COOKIE, MODULE_HEADER, cookieOptions, moduleCookie } from "./lib/session-cookie";
import { siteUrl } from "./lib/site";

// The first gate for every page of the one app (decided 2026-10-23):
//  - no Bishnoi One account here: sign in first (the API checks every request
//    anyway; this only saves a page that would bounce);
//  - a page of a module whose screens are here: the request is marked with
//    that module (MODULE_HEADER, from the path only, so the browser can't pick
//    another), and the module's session is opened on first use (app/auth/enter).
export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  // OAuth codes must never enter login return URLs or the last-page cookie.
  const next = pathname === "/finance/integrations/zoho/callback" ? pathname : pathname + search;
  // The Admin Console's Reports Center is people reports only (2026-10-30): an app's report, and Company KPIs,
  // are opened in that app; old links to them here go there.
  const appReport = pathname.match(/^\/platform\/reports\/(crm|inventory|finance|admin|pharmacy)(\/.*)?$/);
  if (appReport) return NextResponse.redirect(siteUrl(`${moduleByKey(appReport[1])?.path ?? ""}/reports${appReport[2] ?? ""}${search}`, request), 308);
  if (pathname === "/platform/reports/kpis") return NextResponse.redirect(siteUrl(`/crm/kpis${search}`, request), 308);
  // A page in another module's frame (sales orders in the CRM): it talks to its own module, the frame to the frame's.
  const borrowed = borrowedOf(pathname);
  const frame = borrowed ? moduleByKey(borrowed.frame) : null;
  const here = borrowed ? moduleByKey(borrowed.module) : moduleOfPath(pathname);
  // Order links sent before the CRM moved under /crm (/order/<company>/<token>): the customer
  // isn't signed in, so they go straight to the order page, never to the sign-in page.
  if (pathname.startsWith("/order/")) return NextResponse.redirect(siteUrl(`/crm${pathname}${search}`, request), 308);
  // People, roles and teams are kept only in the Admin Console (2026-10-30): each app's own pages for them go there.
  const peoplePage = pathname.match(/^\/(crm|inventory|finance|admin|pharmacy)\/admin\/(users|roles|teams)(?:\/|$)/);
  if (peoplePage) {
    const to = peoplePage[2] === "users" ? "/platform/roles/people" : peoplePage[2] === "roles" ? "/platform/roles" : "/platform/organisation";
    return NextResponse.redirect(siteUrl(to, request), 307);
  }
  // Operators' pages moved out of the Admin Console into Operations (2026-10-30): old links still land.
  const moved = pathname.match(/^\/platform\/(companies|apis|events|operators|people|accounts|jobs)(\/.*)?$/);
  if (moved) return NextResponse.redirect(siteUrl(`/operations/${moved[1]}${moved[2] ?? ""}${search}`, request), 308);
  // Sales orders moved from their own app into the CRM (2026-10-30): old links and stored ones still land.
  if (pathname === "/sales" || pathname.startsWith("/sales/")) return NextResponse.redirect(siteUrl(`/crm${pathname}${search}`, request), 308);
  const headers = new Headers(request.headers);
  headers.delete(MODULE_HEADER);
  headers.delete(FRAME_HEADER);
  // A module's public page (a customer's order link): anyone, signed in or not, still talking to that module's API.
  if (here && here.status === "live" && isPublicPath(here, pathname)) {
    headers.set(MODULE_HEADER, here.key);
    return NextResponse.next({ request: { headers } });
  }
  if (!request.cookies.get(ACCOUNT_COOKIE)?.value) {
    const login = siteUrl("/login", request);
    if (next !== "/") login.searchParams.set("next", next);
    return NextResponse.redirect(login);
  }

  if (!here || here.status !== "live") return NextResponse.next({ request: { headers } });
  // The Admin Console works on the account itself: marked as its module (its API is the Platform's), no session to open.
  if (here.accountOnly) {
    headers.set(MODULE_HEADER, here.key);
    return NextResponse.next({ request: { headers } });
  }

  // The frame's session first (its sidebar is drawn around the page), then the page's own.
  for (const m of frame ? [frame, here] : [here]) {
    if (request.cookies.get(moduleCookie(m.key))?.value) continue;
    const enter = siteUrl(`/auth/enter/${m.key}`, request);
    enter.searchParams.set("next", next);
    return NextResponse.redirect(enter);
  }
  headers.set(MODULE_HEADER, here.key);
  if (frame) headers.set(FRAME_HEADER, frame.key);
  const response = NextResponse.next({ request: { headers } });
  // Where they are, so a module session that ends mid-way reopens and brings them back (app/auth/renew).
  if (request.method === "GET") response.cookies.set(HERE_COOKIE, `${here.key}|${next}`.slice(0, 1000), cookieOptions(8 * 3600));
  return response;
}
