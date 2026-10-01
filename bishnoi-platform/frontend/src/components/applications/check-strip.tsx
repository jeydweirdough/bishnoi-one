import type { Check } from "@/src/lib/types";
import { HEALTH, ago, when } from "@/src/lib/words";

// An application's recent health checks, oldest on the left: each a bar as
// tall as the answer was slow. A check that got no answer stands full height
// and hatched, so "down" reads without the colour. The words under it say the
// same in counts, for anyone who can't see the bars.

const FILL: Record<Check["status"], string> = {
  operational: "bg-filed",
  degraded: "bg-due-today",
  down: "bg-danger bg-[repeating-linear-gradient(45deg,transparent_0_3px,rgb(255_255_255/0.45)_3px_5px)]",
};

export function CheckStrip({ checks }: { checks: Check[] }) {
  if (checks.length === 0) return <p className="text-meta text-ink-3">No checks yet. They start once it has a health address and someone opens a screen.</p>;
  const oldestFirst = [...checks].reverse();
  const slowest = Math.max(...checks.map((c) => c.ms ?? 0), 1);
  const count = (s: Check["status"]) => checks.filter((c) => c.status === s).length;
  const answered = checks.filter((c) => c.ms != null);
  const average = answered.length ? Math.round(answered.reduce((n, c) => n + (c.ms ?? 0), 0) / answered.length) : null;
  const summary = [
    `${count("operational")} fine`,
    count("degraded") ? `${count("degraded")} slow` : null,
    count("down") ? `${count("down")} down` : null,
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <figure>
      <ol aria-label="Recent checks, oldest first" className="flex h-14 items-end gap-[2px] border-b border-rule">
        {oldestFirst.map((c, i) => {
          const share = c.status === "down" || c.ms == null ? 1 : Math.max(0.08, c.ms / slowest);
          const said = `${HEALTH[c.status]}${c.ms != null ? `, ${c.ms} ms` : ""}, ${when(c.checkedAt)}${c.detail ? `: ${c.detail}` : ""}`;
          return (
            <li key={`${i}-${c.checkedAt}`} title={said} className="flex h-full min-w-[3px] flex-1 items-end">
              <span className="sr-only">{said}</span>
              <span aria-hidden className={`block w-full rounded-t-[1px] ${FILL[c.status]}`} style={{ height: `${(share * 100).toFixed(1)}%` }} />
            </li>
          );
        })}
      </ol>
      <figcaption className="mt-2 flex flex-wrap justify-between gap-x-4 gap-y-1 text-meta text-ink-3">
        <span>
          Last {checks.length} checks: {summary}
          {average != null && ` · ${average} ms on average, slowest ${slowest} ms`}
        </span>
        <span>
          {ago(oldestFirst[0].checkedAt)} → {ago(checks[0].checkedAt)}
        </span>
      </figcaption>
    </figure>
  );
}
