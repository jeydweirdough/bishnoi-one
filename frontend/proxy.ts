// The first gate: no session cookie, no pages.
export { proxy } from "@/src/platform/proxy";

// Next reads this from the file itself; a re-exported `config` is ignored.
export const config = {
  matcher: ["/((?!login|_next/static|_next/image|favicon.ico).*)"],
};
