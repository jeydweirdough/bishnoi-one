// Which code is running: the screens' commit (built in by next.config.ts) and
// the API's (from GET /finance/frame). "-dirty": built with changes not yet committed.

export const SCREENS_BUILD = process.env.NEXT_PUBLIC_FINANCE_BUILD || null;
export const SCREENS_BUILT_AT = process.env.NEXT_PUBLIC_FINANCE_BUILT_AT || null;

/** Whether the screens and the API were built from different commits (only when both are known). */
export function buildsDiffer(api: string | null | undefined): boolean {
  const base = (b: string) => b.replace(/-dirty$/, "");
  return Boolean(SCREENS_BUILD && api && base(SCREENS_BUILD) !== base(api));
}
