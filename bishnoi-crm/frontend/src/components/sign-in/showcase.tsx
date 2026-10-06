"use client";

import { useEffect, useState } from "react";

// Beside the CRM's sign-in form: a line drawing of the work the CRM is for (a
// medical rep with today's visit list, the doctor and the pharmacist they call
// on, and the day's route between them), with a card that changes every few
// seconds to show one thing the CRM keeps track of.

const INK = "#141414";
const SAGE = "#a8d69b";
const ROUTE = "#7fb070";

type Slide = { title: string; sub: string; value: number; chip: string; says: string };

const SLIDES: Slide[] = [
  { title: "Customer visits", sub: "18 of 22 this week", value: 82, chip: "On route", says: "Plan your visits and log every call in" },
  { title: "Follow-ups", sub: "5 due today", value: 60, chip: "Due today", says: "Follow up on time, before a customer goes quiet, in" },
  { title: "Quotes", sub: "12 sent this month", value: 75, chip: "Approved", says: "Quote the right price for every customer in" },
];

const EVERY = 6000;

export function Showcase() {
  const [at, setAt] = useState(0);
  const [held, setHeld] = useState(false);

  useEffect(() => {
    if (held || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => setAt((i) => (i + 1) % SLIDES.length), EVERY);
    return () => window.clearInterval(timer);
  }, [held]);

  const slide = SLIDES[at];
  return (
    <aside
      aria-label="What the CRM keeps track of"
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
        {SLIDES.map((s, i) => (
          <button
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
        {slide.says} <span className="font-semibold whitespace-nowrap">Bishnoi One CRM</span>
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
      <circle
        cx="22"
        cy="22"
        r={r}
        fill="none"
        stroke={SAGE}
        strokeWidth="5"
        strokeLinecap="round"
        strokeDasharray={`${(value / 100) * length} ${length}`}
        transform="rotate(-90 22 22)"
      />
      <text x="22" y="25.5" textAnchor="middle" fontSize="10" fontWeight="600" fill={INK}>
        {value}%
      </text>
    </svg>
  );
}

/** The drawing: thin ink lines, sage fills, nothing else. */
function Art() {
  const line = { stroke: INK, strokeWidth: 2.2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg viewBox="0 0 520 440" className="h-auto w-full" aria-hidden>
      <defs>
        <clipPath id="crm-doctor">
          <circle cx="98" cy="128" r="40" />
        </clipPath>
        <clipPath id="crm-pharmacist">
          <circle cx="440" cy="262" r="36" />
        </clipPath>
      </defs>

      {/* The day's route, from the doctor's clinic to the pharmacy, looping as a field day does. */}
      <path
        d="M 132 112 C 160 40, 236 30, 250 84 C 258 118, 216 118, 226 88 C 240 46, 318 34, 344 80 C 362 112, 324 120, 334 92 C 348 56, 430 62, 428 140 C 427 180, 440 200, 440 222"
        fill="none"
        stroke={ROUTE}
        strokeWidth="2.6"
        strokeLinecap="round"
        pathLength={1}
        strokeDasharray="1"
        className="motion-safe:animate-[route-draw_1.8s_ease-out_both]"
      />
      {/* Stops on the way. */}
      {[
        [250, 84],
        [344, 80],
      ].map(([x, y]) => (
        <g key={x} transform={`translate(${x - 10} ${y - 30})`}>
          <path d="M10 28 C 4 20, 0 15, 0 10 A 10 10 0 0 1 20 10 C 20 15, 16 20, 10 28 Z" fill={SAGE} {...line} strokeWidth={1.8} />
          <circle cx="10" cy="10" r="3.4" fill="white" stroke={INK} strokeWidth="1.6" />
        </g>
      ))}

      {/* The rep. */}
      <ellipse cx="260" cy="404" rx="120" ry="10" fill="#e1eddc" />
      <path d="M 182 300 C 186 262, 214 244, 250 242 L 270 242 C 306 244, 334 262, 338 300 L 348 402 L 172 402 Z" fill={SAGE} {...line} />
      <path d="M 248 243 L 260 263 L 272 243" fill="white" {...line} />
      {/* ID lanyard and badge */}
      <path d="M 256 262 L 300 300" fill="none" {...line} strokeWidth={1.6} />
      <rect x="292" y="298" width="24" height="31" rx="4" fill="white" {...line} />
      <path d="M 298 309 h 12 M 298 316 h 8" {...line} strokeWidth={1.6} />
      <rect x="250" y="226" width="20" height="20" fill="white" {...line} />
      <path d="M 224 196 C 214 140, 248 128, 266 138 C 296 132, 308 166, 300 200 C 312 216, 304 238, 292 240 L 290 208 C 284 186, 262 174, 244 180 C 234 192, 232 212, 232 240 C 216 236, 214 212, 224 196 Z" fill={INK} {...line} />
      <ellipse cx="261" cy="196" rx="31" ry="36" fill="white" {...line} />
      <path d="M 238 178 C 248 164, 276 160, 290 178 C 276 172, 256 172, 238 178 Z" fill={INK} {...line} strokeWidth={1.6} />
      <path d="M 245 196 q 6 5 12 0 M 266 196 q 6 5 12 0" fill="none" {...line} />
      <path d="M 261 202 q -3 7 2 9" fill="none" {...line} strokeWidth={1.8} />
      <path d="M 251 217 q 10 8 20 0" fill="none" {...line} />
      {/* Arms, the visit list, hands */}
      <path d="M 192 282 C 174 322, 182 356, 214 360 L 232 346" fill={SAGE} {...line} />
      <path d="M 328 282 C 346 322, 338 356, 306 360 L 288 346" fill={SAGE} {...line} />
      <g transform="rotate(-5 260 352)">
        <rect x="206" y="314" width="108" height="76" rx="9" fill="white" {...line} />
        {[332, 352, 372].map((y, i) => (
          <g key={y}>
            <circle cx="224" cy={y} r="6" fill={i < 2 ? SAGE : "white"} {...line} strokeWidth={1.6} />
            {i < 2 && <path d={`M 221 ${y} l 2.5 2.5 l 4.5 -5`} fill="none" {...line} strokeWidth={1.6} />}
            <path d={`M 238 ${y} h ${i === 1 ? 44 : 60}`} {...line} strokeWidth={1.8} />
          </g>
        ))}
      </g>
      <ellipse cx="212" cy="356" rx="12" ry="10" fill="white" {...line} />
      <ellipse cx="309" cy="350" rx="12" ry="10" fill="white" {...line} />

      {/* The doctor they call on. */}
      <g clipPath="url(#crm-doctor)">
        <circle cx="98" cy="128" r="40" fill={SAGE} />
        <path d="M 62 176 C 66 152, 82 146, 98 146 C 114 146, 130 152, 134 176 Z" fill="white" {...line} />
        <path d="M 90 147 L 98 160 L 106 147" fill="none" {...line} strokeWidth={1.8} />
        <path d="M 84 150 C 80 166, 88 172, 98 168" fill="none" {...line} strokeWidth={1.6} />
        <circle cx="99" cy="168" r="3" fill="white" {...line} strokeWidth={1.6} />
        <circle cx="98" cy="122" r="18" fill="white" {...line} />
        <path d="M 80 118 C 80 100, 116 98, 116 118 C 108 110, 90 110, 80 118 Z" fill={INK} {...line} strokeWidth={1.6} />
        <circle cx="98" cy="110" r="5.5" fill="white" {...line} strokeWidth={1.6} />
        <path d="M 91 124 h 3 M 102 124 h 3" {...line} strokeWidth={2} />
        <path d="M 92 131 q 6 5 12 0" fill="none" {...line} strokeWidth={1.8} />
      </g>
      <circle cx="98" cy="128" r="40" fill="none" {...line} />

      {/* The pharmacist. */}
      <g clipPath="url(#crm-pharmacist)">
        <circle cx="440" cy="262" r="36" fill="white" />
        <path d="M 408 306 C 412 284, 426 278, 440 278 C 454 278, 468 284, 472 306 Z" fill={SAGE} {...line} />
        <circle cx="440" cy="236" r="9" fill={INK} {...line} strokeWidth={1.6} />
        <circle cx="440" cy="258" r="17" fill="white" {...line} />
        <path d="M 423 254 C 424 238, 456 238, 457 254 C 448 246, 432 246, 423 254 Z" fill={INK} {...line} strokeWidth={1.6} />
        <circle cx="433" cy="259" r="5" fill="none" {...line} strokeWidth={1.6} />
        <circle cx="447" cy="259" r="5" fill="none" {...line} strokeWidth={1.6} />
        <path d="M 438 259 h 4" {...line} strokeWidth={1.6} />
        <path d="M 435 268 q 5 4 10 0" fill="none" {...line} strokeWidth={1.8} />
      </g>
      <circle cx="440" cy="262" r="36" fill="none" {...line} />

      {/* A capsule, for the products on the list. */}
      <g transform="rotate(-35 470 120)">
        <rect x="452" y="110" width="40" height="18" rx="9" fill="white" {...line} />
        <path d="M 472 110 v 18" {...line} strokeWidth={1.8} />
        <path d="M 461 110 h 11 v 18 h -11 a 9 9 0 0 1 0 -18 Z" fill={SAGE} {...line} />
      </g>
    </svg>
  );
}
