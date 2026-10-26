/**
 * A report's chart, drawn on the server as SVG: bars or a line, one hue per series (the
 * first series in the brand's sage, a second in ink), the value on hover. The x labels
 * thin out when there are many, so they never overlap.
 */
export type ChartPoint = { x: string; values: (number | null)[] };

const COLOURS = ["#5f8a6f", "#1f2a24", "#c9a24b", "#8aa8c8"];

export function ReportChartView({ kind, labels, points, format }: { kind: "bar" | "line"; labels: string[]; points: ChartPoint[]; format: (v: number) => string }) {
  const W = 760;
  const H = 240;
  const pad = { l: 56, r: 12, t: 12, b: 42 };
  const max = Math.max(1, ...points.flatMap((p) => p.values.map((v) => v ?? 0)));
  const nice = niceCeil(max);
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;
  const step = iw / Math.max(1, points.length);
  const y = (v: number) => pad.t + ih - (v / nice) * ih;
  const every = Math.ceil(points.length / 12);
  const series = labels.length;
  return (
    <figure className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full min-w-[34rem]" role="img" aria-label={`Chart of ${labels.join(" and ")}`}>
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <g key={f}>
            <line x1={pad.l} x2={W - pad.r} y1={y(nice * f)} y2={y(nice * f)} stroke="#e6e2d8" />
            <text x={pad.l - 8} y={y(nice * f) + 4} textAnchor="end" fontSize="10" fill="#7a7a72">
              {format(nice * f)}
            </text>
          </g>
        ))}
        {kind === "bar"
          ? points.map((p, i) =>
              p.values.map((v, s) => {
                const bw = Math.max(2, (step * 0.7) / series);
                const x = pad.l + i * step + step * 0.15 + s * bw;
                const h = ((v ?? 0) / nice) * ih;
                return (
                  <rect key={`${i}-${s}`} x={x} y={pad.t + ih - h} width={bw - 1} height={Math.max(0, h)} rx="2" fill={COLOURS[s % COLOURS.length]}>
                    <title>{`${p.x} · ${labels[s]}: ${format(v ?? 0)}`}</title>
                  </rect>
                );
              }),
            )
          : labels.map((_, s) => (
              <g key={s}>
                <polyline
                  fill="none"
                  stroke={COLOURS[s % COLOURS.length]}
                  strokeWidth="2"
                  points={points.map((p, i) => `${pad.l + i * step + step / 2},${y(p.values[s] ?? 0)}`).join(" ")}
                />
                {points.map((p, i) => (
                  <circle key={i} cx={pad.l + i * step + step / 2} cy={y(p.values[s] ?? 0)} r="3" fill={COLOURS[s % COLOURS.length]}>
                    <title>{`${p.x} · ${labels[s]}: ${format(p.values[s] ?? 0)}`}</title>
                  </circle>
                ))}
              </g>
            ))}
        {points.map((p, i) =>
          i % every === 0 ? (
            <text key={i} x={pad.l + i * step + step / 2} y={H - pad.b + 16} textAnchor="middle" fontSize="10" fill="#7a7a72">
              {p.x.length > 14 ? `${p.x.slice(0, 13)}…` : p.x}
            </text>
          ) : null,
        )}
      </svg>
      {series > 1 && (
        <figcaption className="mt-2 flex flex-wrap gap-4 text-meta text-ink-2">
          {labels.map((l, s) => (
            <span key={l} className="inline-flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm" style={{ background: COLOURS[s % COLOURS.length] }} aria-hidden />
              {l}
            </span>
          ))}
        </figcaption>
      )}
    </figure>
  );
}

/** The axis's top: the next round number above the largest value. */
function niceCeil(v: number): number {
  const p = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}
