/** Running, upcoming, ended or switched off: a promo's or bundle's state, as a small tag. */
export function StateTag({ state }: { state: "running" | "upcoming" | "ended" | "off" }) {
  const look = {
    running: "bg-hema-tint text-ink",
    upcoming: "bg-bench text-ink-2",
    ended: "bg-bench text-ink-3",
    off: "bg-bench text-ink-3",
  }[state];
  const label = { running: "Running", upcoming: "Upcoming", ended: "Ended", off: "Off" }[state];
  return <span className={`inline-block rounded-md px-2 py-0.5 text-meta ${look}`}>{label}</span>;
}
