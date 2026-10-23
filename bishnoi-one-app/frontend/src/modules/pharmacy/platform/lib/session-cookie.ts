// Each Bishnoi One app has its own accounts and its own sign-in, so each keeps its
// own cookie. With one shared name, signing in to one app on the same host
// (localhost in development) would sign you out of the others.
export const SESSION_COOKIE = `bishnoi_${(process.env.NEXT_PUBLIC_BISHNOI_APP ?? process.env.NEXT_PUBLIC_NABHI_APP) ?? "app"}_session`;

// Online, sign-in cookies travel over HTTPS only. ALLOW_HTTP_SIGN_IN=true lets
// them over plain http too, for a server reached only inside the office (e.g.
// http://192.168.1.160:4302) until it has an HTTPS address. Never set it on a
// server the internet can reach: over plain http the session can be read on the way.
export const SECURE_COOKIE = process.env.NODE_ENV === "production" && process.env.ALLOW_HTTP_SIGN_IN !== "true";

// One person per browser (decided 2026-10-21). Bishnoi One Platform marks the
// browser with whoever is signed in to Bishnoi One (HOLDER_COOKIE, the account's
// id, shared across the apps' addresses when they share a parent domain). Each
// app notes whose session it holds (WHO_COOKIE: their account's id, or
// "local:<who held Bishnoi One then>" for a sign-in with this app's own password). When the two differ, someone
// else has signed in on this browser, and the page guard (proxy.ts) ends this
// app's session. NOT_SHARED marks a session opened where the holder couldn't be
// seen (addresses with no common parent, like the .local names): nothing to
// compare against there, so it's left alone.
export const HOLDER_COOKIE = "bishnoi_holder";
export const WHO_COOKIE = `bishnoi_${(process.env.NEXT_PUBLIC_BISHNOI_APP ?? process.env.NEXT_PUBLIC_NABHI_APP) ?? "app"}_who`;
export const NOT_SHARED = "!nohold";
