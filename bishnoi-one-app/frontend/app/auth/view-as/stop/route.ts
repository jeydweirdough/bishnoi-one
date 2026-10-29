import { NextResponse, type NextRequest } from "next/server";
import { MODULES } from "@/src/platform/lib/modules";
import { cookieOptions, viewAsCookie } from "@/src/platform/lib/session-cookie";
import { siteOrigin, siteUrl } from "@/src/platform/lib/site";

// Recovery must work even when preview permissions prevent the module frame
// (and its Stop viewing bar) from rendering. It requires no module API call.
export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin");
  if (origin && origin !== siteOrigin(request.headers, request.url)) return new NextResponse(null, { status: 403 });
  const response = NextResponse.redirect(siteUrl("/", request), 303);
  for (const mod of MODULES) response.cookies.set(viewAsCookie(mod.key), "", cookieOptions(0));
  response.headers.set("Cache-Control", "no-store");
  return response;
}
