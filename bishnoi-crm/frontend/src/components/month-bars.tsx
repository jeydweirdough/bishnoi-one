/**
 * One figure per month as columns: one series, so no legend (the card's title
 * names it). The running month is lighter: it isn't over yet. Hovering a
 * column shows its month and figure; a hidden table has them all for screen
 * readers.
 */
export function MonthBars({
  points,
  label,
  current,
}: {
  points: { month: string; value: number; text: string; monthLabel: string }[];
  /** What the figure is, for the hover and the table: "Revenue won". */
  label: string;
  /** The running month (YYYY-MM). */
  current: string;
}) {
  const top = Math.max(1, ...points.map((p) => p.value));
  const best = points.reduce((b, p) => (p.value > b.value ? p : b), points[0]);
  return (
    <div>
      <div className="flex h-44 items-end gap-1.5 border-b border-rule-strong" role="img" aria-label={`${label} by month`}>
        {points.map((p) => {
          const running = p.month === current;
          return (
            <div key={p.month} className="group relative flex h-full min-w-0 flex-1 flex-col justify-end" title={`${p.monthLabel}: ${p.text}${running ? " so far" : ""}`}>
              {(p === best || running) && p.value > 0 && (
                <span className="mb-1 truncate text-center text-[0.6875rem] font-semibold text-ink-2 tabular-nums">{p.text}</span>
              )}
              <span
                className={`block rounded-t-[4px] transition-colors ${running ? "bg-[#86b6ef]" : "bg-[#2a78d6]"} group-hover:bg-[#1c5cab]`}
                style={{ height: `${Math.max(p.value ? 2 : 0, (100 * p.value) / top)}%` }}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-1.5 flex gap-1.5" aria-hidden>
        {points.map((p) => (
          <span key={p.month} className={`min-w-0 flex-1 truncate text-center text-[0.6875rem] ${p.month === current ? "font-semibold text-ink-2" : "text-ink-3"}`}>
            {p.monthLabel}
          </span>
        ))}
      </div>
      <table className="sr-only">
        <caption>{label} by month</caption>
        <tbody>
          {points.map((p) => (
            <tr key={p.month}>
              <th scope="row">{p.monthLabel}</th>
              <td>{p.text}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
