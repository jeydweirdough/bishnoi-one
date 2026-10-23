import type { ReactNode } from "react";

// An empty list's line drawing and its next step, as on the components page
// (Desktop: bishnoi-one-crm-components.html): ink lines, a sage fill.

const DRAWINGS: Record<"calendar" | "notes" | "people" | "receipt", ReactNode> = {
  receipt: (
    <>
      <path d="M34 14h52v62l-6-5-7 5-7-5-6 5-7-5-6 5-7-5-6 5z" fill="#fff" stroke="#141414" strokeWidth="2" strokeLinejoin="round" />
      <path d="M44 28h32M44 38h24M44 48h28" stroke="#141414" strokeWidth="2" strokeLinecap="round" />
      <rect x="44" y="56" width="32" height="8" rx="3" fill="#a8d69b" stroke="#141414" strokeWidth="2" />
    </>
  ),
  calendar: (
    <>
      <rect x="26" y="18" width="68" height="60" rx="8" fill="#fff" stroke="#141414" strokeWidth="2" />
      <path d="M26 32h68" stroke="#141414" strokeWidth="2" />
      <path d="M40 12v12M80 12v12" stroke="#141414" strokeWidth="2" strokeLinecap="round" />
      <circle cx="60" cy="54" r="11" fill="#a8d69b" stroke="#141414" strokeWidth="2" />
      <path d="M60 49v10M55 54h10" stroke="#141414" strokeWidth="2" strokeLinecap="round" />
    </>
  ),
  notes: (
    <>
      <rect x="30" y="14" width="60" height="66" rx="8" fill="#fff" stroke="#141414" strokeWidth="2" />
      <path d="M42 32h36M42 44h36M42 56h22" stroke="#141414" strokeWidth="2" strokeLinecap="round" />
      <circle cx="84" cy="66" r="12" fill="#a8d69b" stroke="#141414" strokeWidth="2" />
      <path d="M84 60v12M78 66h12" stroke="#141414" strokeWidth="2" strokeLinecap="round" />
    </>
  ),
  people: (
    <>
      <circle cx="48" cy="38" r="12" fill="#fff" stroke="#141414" strokeWidth="2" />
      <path d="M26 74c2-14 11-21 22-21s20 7 22 21" fill="#a8d69b" stroke="#141414" strokeWidth="2" />
      <circle cx="78" cy="42" r="9" fill="#fff" stroke="#141414" strokeWidth="2" />
      <path d="M66 74c1-10 6-16 13-16s13 6 14 16" fill="#fff" stroke="#141414" strokeWidth="2" />
    </>
  ),
};

export function EmptyArt({ art, title, children, action }: { art: keyof typeof DRAWINGS; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="px-4 py-8 text-center">
      <svg width="120" height="92" viewBox="0 0 120 92" className="mx-auto" aria-hidden>
        <ellipse cx="60" cy="84" rx="44" ry="5" fill="#e3eedf" />
        {DRAWINGS[art]}
        <path d="M100 30c8 4 10 14 4 20" fill="none" stroke="#7fb070" strokeWidth="2" strokeLinecap="round" strokeDasharray="3 5" />
      </svg>
      <p className="mt-3 text-base font-semibold text-ink">{title}</p>
      {children && <p className="mx-auto mt-1 max-w-sm text-sm text-ink-3">{children}</p>}
      {action && <div className="mt-4 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}
