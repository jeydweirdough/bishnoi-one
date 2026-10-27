"use client";

import { shorten } from "../lib/short-amount";
import { Tip } from "./tip";

// Figures on KPI cards, charts and summaries, by one rule (decided 2026-10-21):
// from a thousand up they're short, K / M / B / T with up to 2 decimals and the
// currency symbol kept (₱12.2B, ₱1.25M, 4.8K), and the whole amount, with its
// commas, comes up in a tooltip on hover or focus. Detailed tables, quotes and
// invoices show every amount in full. Text that isn't a plain number (45%,
// "—", "3 of 8") is left alone.
//
// The figure cards use it (ui/figures.tsx, the dashboards' Overview), so a
// screen passes the full amount and the card decides how much to show.

// The rule itself is in lib/short-amount.ts, so pages drawn on the server can shorten too.
export { shorten };

/** A figure, short when it's long, with the whole of it on hover (the shared tooltip, ui/tip.tsx). */
export function Amount({ text, className = "" }: { text: string; className?: string }) {
  const short = shorten(text);
  if (!short) return <span className={className}>{text}</span>;
  return (
    <Tip tip={text} dotted strong className={className}>
      {short}
    </Tip>
  );
}

// An amount inside a sentence: "₱1,234.00" or "12,000" (a symbol, or commas).
// Plain numbers without either (a year, "16 open deals") are left as they are.
const IN_TEXT = /[₱$€£¥]\s?\d[\d,]*(?:\.\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?/g;

/**
 * A sentence with amounts in it ("of ₱22,000,000.00 · ₱14,903,225.81 by today"),
 * each amount short by the same rule, each with the whole of it on hover:
 * "of ₱22M · ₱14.9M by today". For the notes under figures and the like.
 */
export function Amounts({ text }: { text: string }) {
  const parts: (string | { amount: string })[] = [];
  let last = 0;
  for (const m of text.matchAll(IN_TEXT)) {
    const at = m.index ?? 0;
    if (at > last) parts.push(text.slice(last, at));
    parts.push({ amount: m[0] });
    last = at + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  if (!parts.some((x) => typeof x !== "string" && shorten(x.amount))) return <>{text}</>;
  return (
    <>
      {parts.map((x, i) => (typeof x === "string" ? x : <Amount key={i} text={x.amount} />))}
    </>
  );
}
