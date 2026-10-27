// The short form of an amount (decided 2026-10-21, see ui/amount.tsx): from a thousand up,
// K / M / B / T with up to 2 decimals and the currency symbol kept. Plain code, so a page drawn
// on the server and the client's <Amount> use the same rule.

const FROM = 1_000;
const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 });

/** "₱12,234,567.89" -> "₱12.23M", "4,820" -> "4.82K"; null under a thousand or when the text isn't a plain amount. */
export function shorten(text: string): string | null {
  const m = /^([^\d\-−]*)([-−]?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(\s*\S{0,3})$/.exec(text.trim());
  if (!m) return null;
  const [, before, sign, whole, cents = "", after] = m;
  const n = Number(`${whole.replace(/,/g, "")}${cents}`);
  if (!Number.isFinite(n) || n < FROM) return null;
  return `${sign}${before}${compact.format(n)}${after}`;
}
