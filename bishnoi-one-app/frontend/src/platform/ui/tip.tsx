"use client";

import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

// One tooltip for the whole app (decided 2026-10-25): the dark bubble the short amounts
// introduced (ui/amount.tsx), now for anything that says less than it means: an icon
// standing for words, a short date, a bar. It rises in after a beat on hover or focus,
// goes on scroll, and is read out as the element's name, so nothing depends on seeing it.

export function Tip({
  tip,
  children,
  className = "",
  dotted = false,
  strong = false,
  passive = false,
}: {
  /** What it means, in words. */
  tip: string;
  children: ReactNode;
  className?: string;
  /** A dotted underline: for text that is a shortened form of the tip (₱381K). */
  dotted?: boolean;
  /** Bold figures in the bubble, for amounts. */
  strong?: boolean;
  /** Around something focusable already (a link, a button): no second tab stop, and it keeps its own name. */
  passive?: boolean;
}) {
  const anchor = useRef<HTMLSpanElement>(null);
  const bubble = useRef<HTMLSpanElement>(null);
  const [at, setAt] = useState<{ x: number; top: number; bottom: number; below: boolean } | null>(null);
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
  // A long tip may not fit above even away from the top bar (a page's explanation on its title): measured once drawn,
  // and put below instead of being cut off at the window's top edge (2026-10-30).
  useLayoutEffect(() => {
    if (!at || at.below || !bubble.current) return;
    if (bubble.current.getBoundingClientRect().top < 4) setAt({ ...at, below: true });
  }, [at]);

  function show() {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      const r = anchor.current?.getBoundingClientRect();
      if (!r) return;
      // Above, unless there's no room (the top bar): then below. Kept inside the window sideways.
      const below = r.top < 64;
      const x = Math.min(Math.max(r.left + r.width / 2, 96), window.innerWidth - 96);
      setAt({ x, top: r.top, bottom: r.bottom, below });
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
      {/* Above a row's covering link (z-[1]), so hovering it shows the tip, not the link. */}
      <span
        ref={anchor}
        tabIndex={passive ? undefined : 0}
        aria-label={passive ? undefined : tip}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        className={`relative z-[1] cursor-default rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-sage ${dotted ? "underline decoration-ink-3/40 decoration-dotted underline-offset-[6px]" : ""} ${className}`}
      >
        {children}
      </span>
      {at &&
        createPortal(
          <span
            ref={bubble}
            role="tooltip"
            style={{ left: at.x, top: at.below ? at.bottom : at.top }}
            className={`pointer-events-none fixed z-[70] -translate-x-1/2 transition-all duration-150 ease-out ${
              at.below ? `pt-2 ${shown ? "opacity-100" : "-translate-y-1 opacity-0"}` : `-translate-y-full pb-2 ${shown ? "opacity-100" : "translate-y-[calc(-100%+4px)] opacity-0"}`
            }`}
          >
            <span className={`relative block max-w-xs rounded-lg bg-ink px-3 py-1.5 text-sm text-white shadow-lg ${strong ? "font-semibold whitespace-nowrap tabular-nums" : "font-medium"}`}>
              {tip}
              {at.below ? (
                <span className="absolute bottom-full left-1/2 -translate-x-1/2 border-x-[6px] border-b-[6px] border-x-transparent border-b-ink" aria-hidden />
              ) : (
                <span className="absolute top-full left-1/2 -translate-x-1/2 border-x-[6px] border-t-[6px] border-x-transparent border-t-ink" aria-hidden />
              )}
            </span>
          </span>,
          document.body,
        )}
    </>
  );
}
