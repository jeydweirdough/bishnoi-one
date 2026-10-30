// Pages that read several modules at once (the Admin Console's Home and Reports Center) open each
// module's session on the way (app/auth/enter). A module that can't be opened (not reachable, not
// set up) must not take the whole page down: with `soft`, the enter route comes back to the page
// with that module listed in `unavailable`, and the page leaves it out with a notice instead of
// sending the person to open it again (which bounced them home, over and over).

/** Where to open `module`'s session, coming back to `next` either way. */
export function enterSoftly(module: string, next: string): string {
  return `/auth/enter/${module}?soft=1&next=${encodeURIComponent(next)}`;
}

/** The modules this page was told it can't open just now (`?unavailable=finance,crm`). */
export function unavailableIn(search: Record<string, string | string[] | undefined>): Set<string> {
  const v = search.unavailable;
  return new Set((typeof v === "string" ? v : "").split(",").map((s) => s.trim()).filter(Boolean));
}

/** `next` with `module` added to its `unavailable` list (a path of this site, kept a path). */
export function markUnavailable(next: string, module: string): string {
  const url = new URL(next, "http://x");
  const list = new Set((url.searchParams.get("unavailable") ?? "").split(",").filter(Boolean));
  list.add(module);
  url.searchParams.set("unavailable", [...list].join(","));
  return `${url.pathname}${url.search}`;
}
