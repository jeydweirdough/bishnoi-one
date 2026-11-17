import { NextResponse, type NextRequest } from "next/server";
import { oneAppUrl } from "@/src/platform/lib/account";
import { openModuleSession } from "@/src/platform/lib/module-session";
import { moduleByKey } from "@/src/platform/lib/modules";
import { markUnavailable } from "@/src/platform/lib/enter";
import { siteUrl } from "@/src/platform/lib/site";
import { ACCOUNT_COOKIE, COMPANY_COOKIE, companyOfToken, cookieOptions, moduleCookie } from "@/src/platform/lib/session-cookie";

// Opens a module's session from the Bishnoi One account when it has none (the proxy sends them here;
// decided 2026-10-23). Since one sign-in (M3, 2026-11-18) every part opens at sign-in
// (src/platform/lib/module-session.ts), so this is the fallback for a session that ran out:
// the Platform hands a pass for the module (it decides who may open it), the
// module's API turns the pass into a session (its /auth/platform), and the
// session is kept in that module's cookie. Then back to the page they asked for.
// Anything refused goes home with the reason, said plainly; with `soft` (a page that reads several
// modules, src/platform/lib/enter.ts) it goes back to that page, which leaves this module out.
export async function GET(request: NextRequest, { params }: { params: Promise<{ module: string }> }) {
  const { module: key } = await params;
  const asked = request.nextUrl.searchParams.get("next") ?? "";
  // Only a page of this site: never somewhere else.
  const next = asked.startsWith("/") && !asked.startsWith("//") ? asked : "/";
  const soft = request.nextUrl.searchParams.get("soft") === "1";
  const home = (notice: string) =>
    NextResponse.redirect(siteUrl(soft ? markUnavailable(next, key) : `/?notice=${encodeURIComponent(notice.slice(0, 300))}`, request));

  const m = moduleByKey(key);
  if (!m || m.status !== "live") return NextResponse.redirect(siteUrl("/", request));
  const account = request.cookies.get(ACCOUNT_COOKIE)?.value;
  const toLogin = () => {
    const login = siteUrl("/login", request);
    login.searchParams.set("next", next);
    const response = NextResponse.redirect(login);
    response.cookies.delete(ACCOUNT_COOKIE);
    return response;
  };
  if (!account) return toLogin();
  const address = request.headers.get("x-forwarded-for")?.split(",")[0].trim() || null;

  const opened = await openModuleSession(m, account, oneAppUrl(request.headers, request.url), address);
  if (!opened.ok) return opened.signedOut ? toLogin() : home(opened.message);
  const session = { accessToken: opened.token, expiresIn: opened.expiresIn };

  const response = NextResponse.redirect(siteUrl(next, request));
  response.cookies.set(moduleCookie(m.key), session.accessToken, cookieOptions(session.expiresIn));
  const company = companyOfToken(session.accessToken);
  if (company) response.cookies.set(COMPANY_COOKIE, company, cookieOptions(400 * 24 * 3600));
  response.headers.set("Cache-Control", "no-store");
  return response;
}
