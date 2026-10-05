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
  const tone = { met: "text-filed", ahead: "text-filed", close: "text-due-today", behind: "text-danger" } as const;
  const ring = { met: "good", ahead: "good", close: "warn", behind: "bad" } as const;
  const marker = target ? Math.min(100, (100 * pace) / target) : null;

  return (
    <div>
      <p className="text-meta text-ink-3">{label}</p>
      {target ? (
        <div className="mt-2 flex items-center gap-4">
          <ProgressRing
            pct={figures.attainment}
            pace={marker}
            tone={state ? ring[state] : "plain"}
            label={`Won ${fmt.peso(won)} of a ${fmt.peso(target)} target; ${fmt.peso(pace)} expected by today`}
          />
          <div className="min-w-0">
            {state && <p className={`text-meta font-semibold ${tone[state]}`}>{words[state]}</p>}
            <p className="text-figure leading-tight text-ink">{fmt.peso(won)}</p>
            <p className="text-meta text-ink-3">of {fmt.peso(target)}</p>
            <p className="mt-1 text-meta text-ink-3">
              {fmt.peso(pace)} expected by today
              {figures.winRate !== null && <> · {figures.winRate}% win rate</>}
            </p>
          </div>
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
