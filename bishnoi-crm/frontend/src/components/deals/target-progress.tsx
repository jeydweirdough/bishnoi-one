import Link from "next/link";
import { ProgressRing } from "../progress-ring";
import type { Format } from "@/src/platform/lib/format";
import type { SalesFigures } from "@/src/platform/lib/types";

/** How far into [start, end) today is, from 0 to 1. */
export function elapsed(start: string, end: string, today: string): number {
  const day = (key: string) => Date.parse(`${key}T00:00:00Z`);
  const span = day(end) - day(start);
  return span > 0 ? Math.min(1, Math.max(0, (day(today) - day(start) + 86_400_000) / span)) : 1;
}

/**
 * Won so far against the period's target, with where it should be by today
 * (the target spread evenly over the period): ahead, on pace, or behind.
 * With no target, it says so and shows what was won.
 */
export function TargetProgress({
  figures,
  start,
  end,
  today,
  fmt,
  label,
  href,
}: {
  figures: Pick<SalesFigures, "wonCentavos" | "wonCount" | "targetCentavos" | "attainment" | "winRate">;
  start: string;
  end: string;
  today: string;
  fmt: Format;
  label: string;
  href?: string;
}) {
  const target = figures.targetCentavos;
  const won = figures.wonCentavos;
  const pace = target ? Math.round(target * elapsed(start, end, today)) : 0;
  const state = !target ? null : won >= target ? "met" : won >= pace ? "ahead" : won >= pace * 0.8 ? "close" : "behind";
  const words = { met: "Target met", ahead: "On pace", close: "Slightly behind pace", behind: "Behind pace" } as const;
  const ring = { met: "good", ahead: "good", close: "warn", behind: "bad" } as const;
  const marker = target ? Math.min(100, (100 * pace) / target) : null;
  const pill = { met: "bg-[#e6f2e1] text-[#3f6f35]", ahead: "bg-[#e6f2e1] text-[#3f6f35]", close: "bg-[#fbf0d9] text-[#8a5a00]", behind: "bg-danger-tint text-danger" } as const;
  const bar = { met: "bg-sage", ahead: "bg-sage", close: "bg-[#e8c27a]", behind: "bg-danger" } as const;

  return (
    <div>
      <p className="text-meta text-ink-3">{label}</p>
      {target ? (
        // As on the components page: the figure, where it stands in words, and a bar with today's pace as a tick.
        <div className="mt-1">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[1.875rem] leading-tight font-semibold tracking-[-0.02em] text-ink">{fmt.peso(won)}</p>
              <p className="text-meta text-ink-3">of {fmt.peso(target)}</p>
            </div>
            <ProgressRing
              size="sm"
              pct={figures.attainment}
              pace={marker}
              tone={state ? ring[state] : "plain"}
              label={`Won ${fmt.peso(won)} of a ${fmt.peso(target)} target; ${fmt.peso(pace)} expected by today`}
            />
          </div>
          {state && (
            <span className={`mt-3 inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-meta font-medium ${pill[state]}`}>
              <span className="size-1.5 rounded-full bg-current" aria-hidden />
              {words[state]}
            </span>
          )}
          <div className="relative mt-3 h-2 rounded-full bg-mint-2" aria-hidden>
            <span className={`absolute inset-y-0 left-0 rounded-full ${bar[state ?? "ahead"]}`} style={{ width: `${Math.min(100, figures.attainment ?? 0)}%` }} />
            {marker !== null && <span className="absolute -top-1 -bottom-1 w-0.5 rounded-full bg-ink" style={{ left: `${marker}%` }} />}
          </div>
          <p className="mt-2 text-meta text-ink-3">
            {fmt.peso(pace)} expected by today
            {figures.winRate !== null && <> · {figures.winRate}% win rate</>}
          </p>
        </div>
      ) : (
        <>
          <p className="mt-1 text-figure text-ink">{fmt.peso(won)}</p>
          <p className="mt-1 text-meta text-ink-3">
            {fmt.plural(figures.wonCount, "deal")} won. No revenue target set for this period
            {href ? (
              <>
                {" "}
                <Link href={href} className="text-ink hover:underline">
                  Set targets
                </Link>
              </>
            ) : null}
            .
          </p>
        </>
      )}
    </div>
  );
}
