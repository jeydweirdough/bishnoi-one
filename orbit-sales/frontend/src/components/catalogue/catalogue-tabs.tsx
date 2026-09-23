import Link from "next/link";
import { can } from "@/src/platform/lib/access";
import type { Me } from "@/src/platform/lib/types";

const TABS = [
  { href: "/products", label: "Products", permission: "products.view" },
  { href: "/promos", label: "Promos", permission: "products.view" },
  { href: "/bundles", label: "Bundles", permission: "products.view" },
  { href: "/prices", label: "Special prices", permission: "products.prices" },
] as const;

/** Products and everything about their price: one place, a tab each. The
 *  rules they're priced by are an admin's, in Settings. */
export function CatalogueTabs({ me, current }: { me: Me; current: (typeof TABS)[number]["href"] }) {
  const tabs = TABS.filter((t) => can(me, t.permission));
  if (tabs.length < 2) return null;
  return (
    <nav aria-label="Products" className="mb-5 flex flex-wrap gap-x-6 gap-y-1 border-b border-rule">
      {tabs.map((t) => (
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
  return <span className={`inline-block rounded-[2px] px-2 py-0.5 text-meta ${look}`}>{label}</span>;
}
