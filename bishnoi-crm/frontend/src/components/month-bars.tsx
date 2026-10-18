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
  fill = false,
}: {
  points: { month: string; value: number; text: string; monthLabel: string }[];
  /** What the figure is, for the hover and the table: "Revenue won". */
  label: string;
  /** The running month (YYYY-MM). */
  current: string;
  /** Grow to the height of the card it's in (beside a taller card), never shorter than usual. */
  fill?: boolean;
}) {
  const top = Math.max(1, ...points.map((p) => p.value));
  return (
    <div className={fill ? "flex flex-1 flex-col" : ""}>
      <div className={`flex items-end gap-1.5 border-b border-rule-strong ${fill ? "min-h-44 flex-1" : "h-44"}`} role="img" aria-label={`${label} by month`}>
        {points.map((p) => {
          const running = p.month === current;
          return (
            <div key={p.month} className="group relative flex h-full min-w-0 flex-1 flex-col justify-end" title={`${p.monthLabel}: ${p.text}${running ? " so far" : ""}`}>
              <span
                className={`block rounded-t-[4px] transition-colors ${running ? "bg-[#cfe8c6]" : "bg-sage"} group-hover:bg-sage-deep`}
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
      <div className="sr-only">
      <table>
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
    </div>
  );
}
