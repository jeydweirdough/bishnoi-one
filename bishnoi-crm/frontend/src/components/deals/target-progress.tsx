import Link from "next/link";
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
  const fill = { met: "bg-filed", ahead: "bg-filed", close: "bg-due-today", behind: "bg-danger" } as const;
  const width = target ? Math.min(100, (100 * won) / target) : 0;
  const marker = target ? Math.min(100, (100 * pace) / target) : 0;

  return (
    <div>
      <p className="flex flex-wrap items-baseline justify-between gap-2 text-meta text-ink-3">
        <span>{label}</span>
        {state && <span className={`font-semibold ${tone[state]}`}>{words[state]}</span>}
      </p>
      <p className="mt-1 text-figure text-ink">
        {fmt.peso(won)}
        {target ? <span className="text-sm font-normal text-ink-3"> of {fmt.peso(target)}</span> : null}
      </p>
      {target ? (
        <>
          <div
            className="relative mt-2 h-2.5 rounded-full bg-bench"
            role="img"
            aria-label={`Won ${fmt.peso(won)} of a ${fmt.peso(target)} target; ${fmt.peso(pace)} expected by today`}
          >
            <span className={`block h-full rounded-full ${state ? fill[state] : "bg-hema"}`} style={{ width: `${width}%` }} />
            <span className="absolute -top-0.5 h-3.5 w-0.5 bg-ink" style={{ left: `calc(${marker}% - 1px)` }} aria-hidden />
          </div>
          <p className="mt-1.5 text-meta text-ink-3">
            {figures.attainment}% of target · {fmt.peso(pace)} expected by today
            {figures.winRate !== null && <> · {figures.winRate}% win rate</>}
          </p>
        </>
      ) : (
        <p className="mt-1 text-meta text-ink-3">
          {fmt.plural(figures.wonCount, "deal")} won. No revenue target set for this period
          {href ? (
            <>
              {" "}
              <Link href={href} className="text-hema hover:underline">
                Set targets
              </Link>
            </>
          ) : null}
          .
        </p>
      )}
    </div>
  );
}
