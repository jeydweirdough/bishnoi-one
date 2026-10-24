// Which code is running: the screens' commit (built in by next.config.ts) and
// the API's (from GET /finance/frame). "-dirty": built with changes not yet committed.

export const SCREENS_BUILD = process.env.NEXT_PUBLIC_FINANCE_BUILD || null;
export const SCREENS_BUILT_AT = process.env.NEXT_PUBLIC_FINANCE_BUILT_AT || null;
/** "vercel": deployed; "local": this computer. */
export const SCREENS_BUILD_SOURCE = process.env.NEXT_PUBLIC_FINANCE_BUILD_SOURCE || "local";

/** Whether the screens and the API were built from different commits, worth a warning:
 *  only when both are deployed builds. On this computer the API restarts by itself when
 *  its files change and the screens don't, so after a commit the two differ while
 *  nothing is wrong (fixed 2026-10-22: it warned falsely on dev machines). */
export function buildsDiffer(api: string | null | undefined, apiSource: string | null | undefined): boolean {
  if (SCREENS_BUILD_SOURCE !== "vercel" || apiSource !== "vercel") return false;
  const base = (b: string) => b.replace(/-dirty$/, "");
  return Boolean(SCREENS_BUILD && api && base(SCREENS_BUILD) !== base(api));
}
