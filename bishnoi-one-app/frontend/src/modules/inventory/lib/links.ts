// Page links Inventory's API hands out (its alerts: "/stock?state=low", …) are
// Inventory's own paths: the API doesn't know where its screens are mounted, and
// the old Inventory app still reads them as they are. In the one app Inventory is
// at /inventory (decided 2026-10-23), so they're put under it where they're loaded.
export function inventoryPage(href: string): string {
  if (!href.startsWith("/") || href.startsWith("//")) return href;
  return href === "/" ? "/inventory" : `/inventory${href}`;
}
