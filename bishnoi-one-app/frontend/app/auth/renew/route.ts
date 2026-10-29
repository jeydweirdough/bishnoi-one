import { NextResponse, type NextRequest } from "next/server";
import { moduleByKey } from "@/src/platform/lib/modules";
import { siteUrl } from "@/src/platform/lib/site";
import { HERE_COOKIE, cookieOptions, moduleCookie } from "@/src/platform/lib/session-cookie";

// Reopened just now and refused again: stop, rather than go round in circles.
const RENEWED = "bishnoi_renewed";

// A module's API said its session has ended (lib/fail.ts sends 401s here). The
// account may still be good, so the module's session is dropped and opened
// again (app/auth/enter), back on the page they were on. No idea where they
// were: sign in again.
export async function GET(request: NextRequest) {
  const [key, ...rest] = (request.cookies.get(HERE_COOKIE)?.value ?? "").split("|");
  const m = moduleByKey(key);
  const where = rest.join("|");
  if (!m) return NextResponse.redirect(siteUrl("/login?expired=1", request));
  // The Admin Console works on the account itself: an ended account signs in again.
  if (m.accountOnly) return NextResponse.redirect(siteUrl(`/login?expired=1&next=${encodeURIComponent(where || m.path)}`, request));
  if (request.cookies.get(RENEWED)?.value === m.key) {
    const notice = `${m.label} keeps ending its session. Try again in a minute, or tell your administrator.`;
    const response = NextResponse.redirect(siteUrl(`/?notice=${encodeURIComponent(notice)}`, request));
    response.cookies.delete(moduleCookie(m.key));
    return response;
  }
  const enter = siteUrl(`/auth/enter/${m.key}`, request);
  enter.searchParams.set("next", where.startsWith(m.path) ? where : m.path);
  const response = NextResponse.redirect(enter);
  response.cookies.delete(moduleCookie(m.key));
  response.cookies.set(RENEWED, m.key, cookieOptions(30));
  return response;
}
