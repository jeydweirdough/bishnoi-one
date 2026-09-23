import { NextResponse, type NextRequest } from "next/server";

// A quick first gate: no session cookie, no pages. The API still checks the
// token on every request; this only saves a round trip to a page that would
// bounce anyway.
export function proxy(request: NextRequest) {
  if (request.cookies.has("crm_session")) return NextResponse.next();
  const login = new URL("/login", request.url);
  const next = request.nextUrl.pathname + request.nextUrl.search;
  if (next !== "/") login.searchParams.set("next", next);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/((?!login|_next/static|_next/image|favicon.ico).*)"],
};
