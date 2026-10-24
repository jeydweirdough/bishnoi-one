"use client";

import { useEffect, useState } from "react";

// Beside the Platform's sign-in form: a line drawing of what the Platform is
// for (Bishnoi One at the middle, linked to each application, each with its
// light on), with a card that changes every few seconds to show one thing the
// Platform looks after. Drawn like the CRM's: thin ink lines, sage fills.

const INK = "#141414";
const SAGE = "#a8d69b";
const LINK = "#7fb070";

export type Slide = { title: string; sub: string; value: number; chip: string; says: string };

const SLIDES: Slide[] = [
  { title: "Applications", sub: "Every one answering", value: 100, chip: "Operational", says: "Watch every application stay up in" },
  { title: "Companies", sub: "Each with its applications", value: 80, chip: "Active", says: "Give each company the applications it needs in" },
  { title: "Support", sub: "Tickets answered on time", value: 70, chip: "On time", says: "Answer every report on time in" },
];

const EVERY = 6000;

/**
 * The panel beside a sign-in form. The Platform's own sign-in speaks to its
 * administrators (the default); the Bishnoi One sign-in (/go) passes slides
 * and a name that speak to everyone who signs in to any application.
 */
export function Showcase({ slides = SLIDES, brand = "Bishnoi One Platform", label = "What the Platform looks after" }: { slides?: Slide[]; brand?: string; label?: string } = {}) {
  const [at, setAt] = useState(0);
  const [held, setHeld] = useState(false);

  useEffect(() => {
    if (held || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => setAt((i) => (i + 1) % slides.length), EVERY);
    return () => window.clearInterval(timer);
  }, [held, slides.length]);

  const slide = slides[at % slides.length];
  return (
    <aside
      aria-label={label}
      className="hidden flex-col items-center justify-center rounded-[28px] bg-[#f1f7ee] px-10 py-12 lg:flex"
      onMouseEnter={() => setHeld(true)}
      onMouseLeave={() => setHeld(false)}
    >
      <div className="relative w-full max-w-[34rem]">
        <Art />
        <div key={at} className="absolute bottom-[1%] left-[-3%] w-[14rem] rounded-[22px] border-[1.5px] border-[#141414] bg-white px-5 pt-4 pb-4 motion-safe:animate-[card-in_500ms_ease-out_both]">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-base font-semibold text-[#141414]">{slide.title}</p>
              <p className="mt-0.5 text-meta text-[#545454]">{slide.sub}</p>
            </div>
            <Ring value={slide.value} />
          </div>
          <span className="mt-3 inline-flex rounded-full border border-[#141414] px-3 py-0.5 text-meta font-medium text-[#141414]">{slide.chip}</span>
        </div>
      </div>

      <div className="mt-8 flex items-center gap-1.5" role="tablist" aria-label="Pick one">
        {slides.map((s, i) => (
          <button suppressHydrationWarning
            key={s.title}
            type="button"
            role="tab"
            aria-selected={i === at}
            aria-label={s.title}
            onClick={() => setAt(i)}
            className={`h-2 rounded-full transition-all focus-visible:ring-2 focus-visible:ring-[#7fb070] focus-visible:outline-none ${i === at ? "w-6 bg-[#141414]" : "w-2 bg-[#c9c9c9] hover:bg-[#9a9a9a]"}`}
          />
        ))}
      </div>
      <p className="mt-6 max-w-[26rem] text-center text-[1.45rem] leading-snug text-[#141414]" aria-live="polite">
        {slide.says} <span className="font-semibold whitespace-nowrap">{brand}</span>
      </p>
    </aside>
  );
}

function Ring({ value }: { value: number }) {
  const r = 17;
  const length = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 44 44" className="size-12 shrink-0" role="img" aria-label={`${value}%`}>
      <circle cx="22" cy="22" r={r} fill="none" stroke="#e3eedf" strokeWidth="5" />
      <circle cx="22" cy="22" r={r} fill="none" stroke={SAGE} strokeWidth="5" strokeLinecap="round" strokeDasharray={`${(value / 100) * length} ${length}`} transform="rotate(-90 22 22)" />
      <text x="22" y="25.5" textAnchor="middle" fontSize="10" fontWeight="600" fill={INK}>
        {value}%
      </text>
    </svg>
  );
}

// The applications around the middle: where each sits, and what's drawn in it.
const APPS: { x: number; y: number; draw: "chart" | "box" | "cross" | "coin" | "doc" }[] = [
  { x: 120, y: 92, draw: "chart" }, // the CRM's results
  { x: 400, y: 92, draw: "box" }, // Inventory's stock
  { x: 452, y: 250, draw: "cross" }, // Pharmacy
  { x: 260, y: 372, draw: "coin" }, // Finance
  { x: 68, y: 250, draw: "doc" }, // Executive Admin's papers
];

/** The drawing: Bishnoi One in the middle, linked to each application, each light on. */
function Art() {
  const line = { stroke: INK, strokeWidth: 2.2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const mid = { x: 260, y: 220 };
  return (
    <svg viewBox="0 0 520 440" className="h-auto w-full" aria-hidden>
      {/* The links: each application's line to the middle, gently curved. */}
      {APPS.map((a, i) => (
        <path
          key={`l${i}`}
          d={`M ${mid.x} ${mid.y} Q ${(mid.x + a.x) / 2 + (i % 2 ? 26 : -26)} ${(mid.y + a.y) / 2} ${a.x} ${a.y}`}
          fill="none"
          stroke={LINK}
          strokeWidth="2.6"
          strokeLinecap="round"
          strokeDasharray="1 9"
        />
      ))}

      {/* The middle: Bishnoi One. */}
      <circle cx={mid.x} cy={mid.y} r="62" fill={SAGE} {...line} />
      <circle cx={mid.x} cy={mid.y} r="44" fill="white" {...line} />
      <path d={`M ${mid.x - 18} ${mid.y + 14} L ${mid.x} ${mid.y - 22} L ${mid.x + 18} ${mid.y + 14} Z`} fill="none" {...line} />
      <circle cx={mid.x} cy={mid.y + 2} r="5" fill={INK} />

      {/* The applications, each a round window with its own sign, and its light. */}
      {APPS.map((a, i) => (
        <g key={`a${i}`}>
          <circle cx={a.x} cy={a.y} r="34" fill="white" {...line} />
          <Sign kind={a.draw} x={a.x} y={a.y} line={line} />
          <circle cx={a.x + 25} cy={a.y - 25} r="7" fill={SAGE} {...line} strokeWidth={1.8} />
        </g>
      ))}
    </svg>
  );
}

function Sign({ kind, x, y, line }: { kind: "chart" | "box" | "cross" | "coin" | "doc"; x: number; y: number; line: Record<string, unknown> }) {
  if (kind === "chart")
    return (
      <g>
        <path d={`M ${x - 14} ${y + 12} v -10 M ${x - 4} ${y + 12} v -18 M ${x + 6} ${y + 12} v -6 M ${x + 16} ${y + 12} v -14`} {...line} strokeWidth={3} />
      </g>
    );
  if (kind === "box")
    return (
      <g>
        <path d={`M ${x - 15} ${y - 6} L ${x} ${y - 14} L ${x + 15} ${y - 6} L ${x + 15} ${y + 12} L ${x - 15} ${y + 12} Z`} fill={SAGE} {...line} />
        <path d={`M ${x - 15} ${y - 6} L ${x + 15} ${y - 6}`} {...line} />
      </g>
    );
  if (kind === "cross") return <path d={`M ${x - 5} ${y - 16} h 10 v 11 h 11 v 10 h -11 v 11 h -10 v -11 h -11 v -10 h 11 Z`} fill={SAGE} {...line} />;
  if (kind === "coin")
    return (
      <g>
        <circle cx={x} cy={y} r="15" fill={SAGE} {...line} />
        <path d={`M ${x - 5} ${y - 7} h 7 a 4 4 0 0 1 0 8 h -7 M ${x - 5} ${y - 7} v 15`} fill="none" {...line} strokeWidth={1.8} />
      </g>
    );
  return (
    <g>
      <rect x={x - 12} y={y - 16} width="24" height="32" rx="3" fill="white" {...line} />
      <path d={`M ${x - 6} ${y - 6} h 12 M ${x - 6} ${y + 1} h 12 M ${x - 6} ${y + 8} h 7`} {...line} strokeWidth={1.8} />
    </g>
  );
}
