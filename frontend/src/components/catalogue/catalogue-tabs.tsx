import Link from "next/link";

const TABS = [
  { href: "/products", label: "Products" },
  { href: "/promos", label: "Promos" },
  { href: "/bundles", label: "Bundles" },
  { href: "/pricing", label: "Pricing rules" },
] as const;

/** Products and services, and what decides their prices on a quote: one section, four pages. */
export function CatalogueTabs({ current }: { current: (typeof TABS)[number]["href"] }) {
  return (
    <nav aria-label="Catalogue" className="mb-5 flex flex-wrap gap-x-6 gap-y-1 border-b border-rule">
      {TABS.map((t) => (
        <Link
          key={t.href}
          href={t.href}
          aria-current={t.href === current ? "page" : undefined}
          className={`-mb-px border-b-2 px-1 pb-2 text-sm ${
            t.href === current ? "border-hema font-semibold text-hema" : "border-transparent text-ink-2 hover:text-ink"
          }`}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  );
}

/** Running, upcoming, ended or switched off: a promo's or bundle's state, as a small tag. */
export function StateTag({ state }: { state: "running" | "upcoming" | "ended" | "off" }) {
  const look = {
    running: "bg-hema-tint text-hema",
    upcoming: "bg-bench text-ink-2",
    ended: "bg-bench text-ink-3",
    off: "bg-bench text-ink-3",
  }[state];
  const label = { running: "Running", upcoming: "Upcoming", ended: "Ended", off: "Off" }[state];
  return <span className={`inline-block rounded-full px-2 py-0.5 text-meta ${look}`}>{label}</span>;
}
