// Page links Executive Admin's API hands out (its expiry summaries' href, a
// renewal's actionPath) are Admin's own paths, "/vehicles/…": the API doesn't
// know where its screens are mounted, and the old Admin app still reads them as
// they are. In the one app Admin is at /admin (decided 2026-10-23), so they're
// put under it here, where they're shown. They always come from the API, so
// they're always prefixed (Admin has pages of its own at /admin/admin/… too).
export function adminPage(href: string): string {
  if (!href.startsWith("/") || href.startsWith("//")) return href;
  return href === "/" ? "/admin" : `/admin${href}`;
}
