import { NextResponse, type NextRequest } from "next/server";
import { AccountError, accountCall, oneAppUrl } from "@/src/platform/lib/account";
import { moduleApi } from "@/src/platform/lib/api";
import { moduleByKey } from "@/src/platform/lib/modules";
import { ACCOUNT_COOKIE, COMPANY_COOKIE, companyOfToken, cookieOptions, moduleCookie } from "@/src/platform/lib/session-cookie";

// Opens a module's session from the Bishnoi One account, the first time
// someone opens that module (the proxy sends them here; decided 2026-10-23):
// the Platform hands a pass for the module (it decides who may open it), the
// module's API turns the pass into a session (its /auth/platform), and the
// session is kept in that module's cookie. Then back to the page they asked for.
// Anything refused goes home with the reason, said plainly.
export async function GET(request: NextRequest, { params }: { params: Promise<{ module: string }> }) {
  const { module: key } = await params;
  const asked = request.nextUrl.searchParams.get("next") ?? "";
  // Only a page of this site: never somewhere else.
  const next = asked.startsWith("/") && !asked.startsWith("//") ? asked : "/";
  const home = (notice: string) => NextResponse.redirect(new URL(`/?notice=${encodeURIComponent(notice.slice(0, 300))}`, request.url));

  const m = moduleByKey(key);
  if (!m || m.status !== "live") return NextResponse.redirect(new URL("/", request.url));
  const account = request.cookies.get(ACCOUNT_COOKIE)?.value;
  const toLogin = () => {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", next);
    const response = NextResponse.redirect(login);
    response.cookies.delete(ACCOUNT_COOKIE);
    return response;
  };
  if (!account) return toLogin();
  const address = request.headers.get("x-forwarded-for")?.split(",")[0].trim() || null;

  let pass: string;
  try {
    pass = (await accountCall<{ pass: string }>("/identity/pass", { app: m.appKey, returnTo: `${oneAppUrl(request.headers, request.url)}/auth/platform` }, account, address)).pass;
  } catch (error) {
    if (error instanceof AccountError && error.status === 401) return toLogin();
    return home(error instanceof Error ? error.message : `${m.label} couldn't be opened.`);
  }

  let session: { accessToken: string; expiresIn: number };
  try {
    const response = await fetch(`${await moduleApi(m)}/auth/platform`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(address ? { "X-Forwarded-For": address } : {}) },
      body: JSON.stringify({ pass }),
      cache: "no-store",
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) return home(typeof data?.detail === "string" ? data.detail : `${m.label} didn't open (error ${response.status}).`);
    session = data;
  } catch {
    return home(`${m.label} can't be reached just now. Try again in a minute.`);
  }

  const response = NextResponse.redirect(new URL(next, request.url));
  response.cookies.set(moduleCookie(m.key), session.accessToken, cookieOptions(session.expiresIn));
  const company = companyOfToken(session.accessToken);
  if (company) response.cookies.set(COMPANY_COOKIE, company, cookieOptions(400 * 24 * 3600));
  response.headers.set("Cache-Control", "no-store");
  return response;
}
