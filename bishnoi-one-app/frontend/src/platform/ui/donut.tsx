import Link from "next/link";

// A whole split into a few parts (people by status): a ring with the total in its middle, then each part
// as a labelled bar with its count, so nothing is told by colour alone. Drawn on the server as SVG; the
// value on hover. A small gap of the card's colour between segments keeps neighbours apart.

export type DonutPart = { label: string; value: number; colour: string; href?: string };

export function Donut({ parts, caption }: { parts: DonutPart[]; caption: string }) {
  const total = parts.reduce((s, p) => s + p.value, 0);
  const r = 52;
  const c = 2 * Math.PI * r;
  const gap = parts.filter((p) => p.value > 0).length > 1 ? 3 : 0;
  let at = 0;
  return (
    <div>
      <figure className="flex justify-center">
        <svg viewBox="0 0 140 140" className="size-44" role="img" aria-label={`${caption}: ${parts.map((p) => `${p.label} ${p.value}`).join(", ")}`}>
          <circle cx="70" cy="70" r={r} fill="none" stroke="#efece4" strokeWidth="14" />
          {total > 0 &&
            parts.map((p) => {
              const len = (p.value / total) * c;
              const seg = (
                <circle
                  key={p.label}
                  cx="70"
                  cy="70"
                  r={r}
                  fill="none"
                  stroke={p.colour}
                  strokeWidth="14"
                  strokeDasharray={`${Math.max(0, len - gap)} ${c}`}
                  strokeDashoffset={-at}
                  transform="rotate(-90 70 70)"
                >
                  <title>{`${p.label}: ${p.value}`}</title>
                </circle>
              );
              at += len;
              return p.value > 0 ? seg : null;
            })}
          <text x="70" y="68" textAnchor="middle" fontSize="24" fontWeight="600" fill="#1f2a24">
            {total}
          </text>
          <text x="70" y="86" textAnchor="middle" fontSize="10" fill="#7a7a72">
            {caption}
          </text>
        </svg>
      </figure>
      <ul className="mt-4 space-y-3">
        {parts.map((p) => {
          const row = (
            <>
              <span className="flex items-baseline justify-between gap-3 text-sm">
                <span className="text-ink">{p.label}</span>
                <span className="shrink-0 text-ink-3 tabular-nums">{p.value}</span>
              </span>
              <span className="mt-1 block h-2 overflow-hidden rounded-full bg-rule" aria-hidden>
                <span className="block h-full rounded-full" style={{ width: `${total ? Math.round((p.value / total) * 100) : 0}%`, background: p.colour }} />
              </span>
            </>
          );
          return (
            <li key={p.label}>
              {p.href ? (
                <Link href={p.href} className="block rounded-md hover:bg-bench">
                  {row}
                </Link>
              ) : (
                row
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
