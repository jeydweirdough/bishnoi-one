// A page address the API gives (a notification's link, a calendar item's): the API names
// Finance's pages as they were in its own app ("/vouchers/…"); in the one app they're under
// /finance (moved 2026-10-24). Addresses already there, and outside ones, are left alone.
export function screen(link: string): string {
  if (!link.startsWith("/") || link.startsWith("//") || link === "/finance" || link.startsWith("/finance/") || link.startsWith("/finance?")) return link;
  return link === "/" ? "/finance" : `/finance${link}`;
}
