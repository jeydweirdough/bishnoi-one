import { NextResponse, type NextRequest } from "next/server";
import { moduleByKey } from "@/src/platform/lib/modules";
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
  if (!m) return NextResponse.redirect(new URL("/login?expired=1", request.url));
  // The staff console's session ended: its own sign-in page, back to where they were.
  if (m.staffSignIn) {
    const login = new URL(m.staffSignIn, request.url);
    login.searchParams.set("next", where.startsWith(m.path) ? where : m.path);
    const response = NextResponse.redirect(login);
    response.cookies.delete(moduleCookie(m.key));
    return response;
  }
  if (request.cookies.get(RENEWED)?.value === m.key) {
    const notice = `${m.label} keeps ending its session. Try again in a minute, or tell your administrator.`;
    const response = NextResponse.redirect(new URL(`/?notice=${encodeURIComponent(notice)}`, request.url));
    response.cookies.delete(moduleCookie(m.key));
    return response;
  }
  const enter = new URL(`/auth/enter/${m.key}`, request.url);
  enter.searchParams.set("next", where.startsWith(m.path) ? where : m.path);
  const response = NextResponse.redirect(enter);
  response.cookies.delete(moduleCookie(m.key));
  response.cookies.set(RENEWED, m.key, cookieOptions(30));
  return response;
}
