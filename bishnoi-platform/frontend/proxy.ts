// The first gate: no session cookie, no pages. The API still checks the
// token on every request; this only saves a round trip.
export { proxy } from "@/src/platform/proxy";

// Next reads this field from the file itself, so it is written here rather
// than re-exported — a re-exported `config` is ignored and the default used.
export const config = {
  matcher: ["/((?!login|busy|unavailable|go$|go/signout$|go/hold$|_next/static|_next/image|favicon.ico|icon.png|apple-icon.png|brand/).*)"],
};
