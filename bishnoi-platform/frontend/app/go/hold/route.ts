import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";
import { ACCOUNT_COOKIE, accountCall, HOLDER_COOKIE, HOLDER_DOMAIN } from "@/src/go/account";
import { loadAddresses } from "@/src/platform/lib/addresses";
import { appUrl, type AppName } from "@/src/platform/lib/apps";
import { SECURE_COOKIE } from "@/src/platform/lib/session-cookie";

// On the way from /go to an application with its pass: marks this browser with
// whoever is signed in to Bishnoi One (HOLDER_COOKIE, src/go/account.ts), so
// every app can end a session that belongs to somebody else. Only ever on to
// one of the Bishnoi One apps, so the link can't send anyone elsewhere.
const EVERY_APP: AppName[] = ["exec", "crm", "finance", "inventory", "regulatory", "inlicensing", "pharmacy", "platform"];

export async function GET(request: NextRequest) {
  const to = request.nextUrl.searchParams.get("to") ?? "";
  await loadAddresses();
  const ours = new Set(EVERY_APP.map((a) => { try { return new URL(appUrl(a)).origin; } catch { return ""; } }));
  let target: URL;
  try {
    target = new URL(to);
    if (!["http:", "https:"].includes(target.protocol) || !ours.has(target.origin)) throw new Error("not ours");
  } catch {
    return NextResponse.redirect(new URL("/go", request.url));
  }
  const response = NextResponse.redirect(target);
  const token = (await cookies()).get(ACCOUNT_COOKIE)?.value;
  const me = token ? await accountCall<{ id: string }>("/identity/me", undefined, token).catch(() => null) : null;
  if (me?.id) {
    response.cookies.set(HOLDER_COOKIE, me.id, { httpOnly: true, sameSite: "lax", secure: SECURE_COOKIE, path: "/", domain: HOLDER_DOMAIN, maxAge: 30 * 24 * 3600 });
  }
  response.headers.set("Cache-Control", "no-store");
  return response;
}
