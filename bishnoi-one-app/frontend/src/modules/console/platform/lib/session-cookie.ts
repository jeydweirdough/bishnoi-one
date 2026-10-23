// Each Bishnoi One app has its own accounts and its own sign-in, so each keeps its
// own cookie. With one shared name, signing in to one app on the same host
// (localhost in development) would sign you out of the others.
export const SESSION_COOKIE = `bishnoi_${(process.env.NEXT_PUBLIC_BISHNOI_APP ?? process.env.NEXT_PUBLIC_NABHI_APP) ?? "app"}_session`;

// Online, sign-in cookies travel over HTTPS only. ALLOW_HTTP_SIGN_IN=true lets
// them over plain http too, for a server reached only inside the office (e.g.
// http://192.168.1.160:4305) until it has an HTTPS address. Never set it on a
// server the internet can reach: over plain http the session can be read on the way.
export const SECURE_COOKIE = process.env.NODE_ENV === "production" && process.env.ALLOW_HTTP_SIGN_IN !== "true";
