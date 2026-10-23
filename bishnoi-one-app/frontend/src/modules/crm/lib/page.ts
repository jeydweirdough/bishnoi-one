// Page links the CRM's API hands out (its attention prompts, search results, a
// quote's customer) are the CRM's own paths, "/companies/…": the API doesn't know
// where its screens are mounted, and the old CRM app still reads them as they
// are. In the one app the CRM is at /crm (decided 2026-10-23), so they're put
// under it here, where they're loaded. A link already under /crm, or one that
// leaves the site, is left as it is.

/** A CRM page path from the API, under /crm. */
export function crmPage(href: string): string;
export function crmPage(href: string | null | undefined): string | null | undefined;
export function crmPage(href: string | null | undefined) {
  if (!href || !href.startsWith("/") || href.startsWith("//")) return href;
  if (href === "/crm" || href.startsWith("/crm/") || href.startsWith("/crm?")) return href;
  return href === "/" ? "/crm" : `/crm${href}`;
}

/** The same for each of a list's `href`s (attention prompts). */
export const withCrmPages = <T extends { href: string }>(items: T[]): T[] => items.map((x) => ({ ...x, href: crmPage(x.href) }));
