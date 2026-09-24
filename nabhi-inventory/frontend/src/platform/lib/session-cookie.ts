// Each Nabhi app has its own accounts and its own sign-in, so each keeps its
// own cookie. With one shared name, signing in to one app on the same host
// (localhost in development) would sign you out of the others.
export const SESSION_COOKIE = `nabhi_${process.env.NEXT_PUBLIC_NABHI_APP ?? "app"}_session`;
