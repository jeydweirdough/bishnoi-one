import Link from "next/link";
import type { ReactNode } from "react";
import { Amount, Amounts } from "./amount";
import { Bone } from "./skeleton";

// The pieces figures are drawn with, one of each, used by every page: the
// pill that says where something stands, the ring that shows how far along it
// is, the tile and the card a figure sits in. A page says what the figure is;
// these say how it looks.

export type Tone = "good" | "warn" | "bad" | "plain" | "ink";

const TONES: Record<Tone, string> = {
  good: "bg-[#e6f2e1] text-[#3f6f35]",
  warn: "bg-[#fbf0d9] text-[#8a5a00]",
  bad: "bg-danger-tint text-danger",
  plain: "bg-bench text-ink-3",
  ink: "border border-ink bg-sheet text-ink",
};

/** Where something stands, in words: "On pace", "Behind", "Waiting". The dot is for the eye; the words say it. */
export function Pill({ tone = "plain", dot = true, className = "", children }: { tone?: Tone; dot?: boolean; className?: string; children: ReactNode }) {
  return (
    <span className={`inline-flex h-6 items-center gap-1.5 rounded-md px-2.5 text-meta font-medium whitespace-nowrap ${TONES[tone]} ${className}`}>
      {dot && <span className="size-1.5 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}

const RING_SIZE = { sm: "size-10", md: "size-12", lg: "size-14" } as const;

/** How far along, as a mint ring (the words beside it say the figure). Over 100 shows full. */
export function Ring({ pct, size = "md" }: { pct: number; size?: keyof typeof RING_SIZE }) {
  const filled = Math.max(0, Math.min(100, pct));
  return (
    <svg viewBox="0 0 44 44" className={`${RING_SIZE[size]} shrink-0`} aria-hidden>
      <circle cx="22" cy="22" r="17" fill="none" stroke="#e3eedf" strokeWidth="5" />
      <circle cx="22" cy="22" r="17" fill="none" stroke="#a8d69b" strokeWidth="5" strokeLinecap="round" strokeDasharray={`${(filled / 100) * 106.8} 106.8`} transform="rotate(-90 22 22)" />
    </svg>
  );
}

export type Figure = {
  value: string;
  label: string;
  note: string;
  ring?: number | null;
  href?: string;
  /** Needs doing (overdue, waiting): the figure in red, the note in amber. */
  alert?: boolean;
  /** Where it stands, in words, as a pill under the label: "Behind", "On target". */
  pill?: { text: string; tone: Exclude<Tone, "ink"> };
};

function Linked({ href, className, children }: { href?: string; className: string; children: ReactNode }) {
  return href ? (
    <Link href={href} className={`${className} transition-colors hover:border-ink`}>
      {children}
    </Link>
  ) : (
    <div className={className}>{children}</div>
  );
}

/** One figure in a card: the number large, then what it is, then how it compares. */
export function FigureCard({ figure: f, first = false }: { figure: Figure; first?: boolean }) {
  return (
    <Linked href={f.href} className={`block rounded-xl bg-sheet px-5 py-4 ${first ? "border-[1.5px] border-ink" : "border border-rule"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[1.875rem] leading-tight font-semibold tracking-[-0.02em] text-ink tabular-nums"><Amount text={f.value} /></p>
          <p className="mt-1 text-sm font-medium text-ink">{f.label}</p>
          {f.pill && (
            <Pill tone={f.pill.tone} className="mt-1.5">
              {f.pill.text}
            </Pill>
          )}
        </div>
        {f.ring !== undefined && f.ring !== null && <Ring pct={f.ring} />}
      </div>
      <p className={`mt-1 text-meta ${f.alert ? "font-semibold text-due-today" : "text-ink-3"}`}><Amounts text={f.note} /></p>
    </Linked>
  );
}

/** The same card while its number is on the way: what it counts now, the number when it lands. */
export function FigureCardLoading({ label, first = false }: { label: string; first?: boolean }) {
  return (
    <div className={`block rounded-xl bg-sheet px-5 py-4 ${first ? "border-[1.5px] border-ink" : "border border-rule"}`}>
      <Bone className="my-1.5 h-7 w-28" />
      <p className="mt-1 text-sm font-medium text-ink">{label}</p>
      <Bone className="mt-2 h-3 w-36" />
    </div>
  );
}

/** A smaller figure, as a tile among others (under a lead figure, in a grid of counts). */
export function Tile({ figure: f }: { figure: Figure }) {
  return (
    <Linked href={f.href} className={`block min-w-0 rounded-lg border bg-sheet px-4 py-3 ${f.alert ? "border-[#f0c9c6]" : "border-rule"}`}>
      <span className={`block truncate text-[1.375rem] leading-tight font-semibold tabular-nums ${f.alert ? "text-danger" : "text-ink"}`}><Amount text={f.value} /></span>
      <span className="mt-1 block text-sm font-medium text-ink">{f.label}</span>
      <span className="mt-0.5 block text-meta text-ink-3">
        {f.pill ? `${f.pill.text} · ` : ""}
        <Amounts text={f.note} />
      </span>
    </Linked>
  );
}

/** The figure a page leads with, in its own mint block: large, where it stands, its ring. */
export function LeadFigure({ figure: f }: { figure: Figure }) {
  return (
    <Linked href={f.href} className="flex items-start justify-between gap-3 rounded-xl bg-mint px-4 py-3.5 hover:bg-mint-2">
      <span className="min-w-0">
        <span className="block text-[2.25rem] leading-tight font-semibold tracking-[-0.02em] text-ink tabular-nums"><Amount text={f.value} /></span>
        <span className="mt-1 block text-sm font-medium text-ink">{f.label}</span>
        {f.pill && (
          <Pill tone={f.pill.tone} className="mt-1.5">
            {f.pill.text}
          </Pill>
        )}
        <span className="mt-1 block text-meta text-ink-3"><Amounts text={f.note} /></span>
      </span>
      {f.ring !== undefined && f.ring !== null && <Ring pct={f.ring} size="lg" />}
    </Linked>
  );
}
