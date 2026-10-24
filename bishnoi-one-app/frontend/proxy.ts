// The first gate: no Bishnoi One account, no pages; and each module's page is
// marked with its module (src/platform/proxy.ts).
export { proxy } from "@/src/platform/proxy";

// Next reads this field from the file itself, so it is written here rather
// than re-exported — a re-exported `config` is ignored and the default used.
export const config = {
  matcher: ["/((?!login|auth/|busy|unavailable|_next/static|_next/image|favicon.ico|icon.png|apple-icon.png|brand/).*)"],
};
