/** Joins class names, leaving out the empty ones (what Gauge UI calls `cn`). */
export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}
