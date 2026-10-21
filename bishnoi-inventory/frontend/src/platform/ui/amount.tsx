"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

// Figures on KPI cards, charts and summaries, by one rule (decided 2026-10-21):
// from a thousand up they're short, K / M / B / T with up to 2 decimals and the
// currency symbol kept (₱12.2B, ₱1.25M, 4.8K), and the whole amount, with its
// commas, comes up in a tooltip on hover or focus. Detailed tables, quotes and
// invoices show every amount in full. Text that isn't a plain number (45%,
// "—", "3 of 8") is left alone.
//
// The figure cards use it (ui/figures.tsx, the dashboards' Overview), so a
// screen passes the full amount and the card decides how much to show.

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

/** A figure, short when it's long, with the whole of it on hover. */
export function Amount({ text, className = "" }: { text: string; className?: string }) {
  const short = shorten(text);
  const anchor = useRef<HTMLSpanElement>(null);
  const [at, setAt] = useState<{ x: number; y: number } | null>(null);
  const [shown, setShown] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!at) return;
    const hide = () => {
      setShown(false);
      setAt(null);
    };
    window.addEventListener("scroll", hide, true);
    window.addEventListener("resize", hide);
    return () => {
      window.removeEventListener("scroll", hide, true);
      window.removeEventListener("resize", hide);
    };
  }, [at]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  if (!short) return <span className={className}>{text}</span>;

  function show() {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      const r = anchor.current?.getBoundingClientRect();
      if (!r) return;
      setAt({ x: r.left + r.width / 2, y: r.top });
      // The next frame, so it fades and rises in rather than appearing.
      requestAnimationFrame(() => setShown(true));
    }, 120);
  }
  function hide() {
    window.clearTimeout(timer.current);
    setShown(false);
    timer.current = window.setTimeout(() => setAt(null), 150);
  }

  return (
    <>
      <span
        ref={anchor}
        tabIndex={0}
        aria-label={text}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        className={`cursor-default rounded-sm underline decoration-ink-3/40 decoration-dotted underline-offset-[6px] outline-none focus-visible:ring-2 focus-visible:ring-sage ${className}`}
      >
        {short}
      </span>
      {at &&
        createPortal(
          <span
            role="tooltip"
            style={{ left: at.x, top: at.y }}
            className={`pointer-events-none fixed z-[70] -translate-x-1/2 -translate-y-full pb-2 transition-all duration-150 ease-out ${shown ? "opacity-100" : "translate-y-[calc(-100%+4px)] opacity-0"}`}
          >
            <span className="relative block rounded-lg bg-ink px-3 py-1.5 text-sm font-semibold whitespace-nowrap text-white tabular-nums shadow-lg">
              {text}
              <span className="absolute top-full left-1/2 -translate-x-1/2 border-x-[6px] border-t-[6px] border-x-transparent border-t-ink" aria-hidden />
            </span>
          </span>,
          document.body,
        )}
    </>
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
