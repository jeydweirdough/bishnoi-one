// The calendar's date ranges, for the page that loads them (the server) and the calendar itself.

/** The first and the day after the last of a month ("2026-10"), as YYYY-MM-DD. */
export function monthRange(month: string): { from: string; to: string } {
  const [y, m] = month.split("-").map(Number);
  const next = m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, "0")}`;
  return { from: `${month}-01`, to: `${next}-01` };
}

/** The Monday of the week a day is in, and the Monday after, as YYYY-MM-DD. */
export function weekRange(day: string): { from: string; to: string } {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
  const from = d.toISOString().slice(0, 10);
  d.setUTCDate(d.getUTCDate() + 7);
  return { from, to: d.toISOString().slice(0, 10) };
}
