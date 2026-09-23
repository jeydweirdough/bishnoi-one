import Link from "next/link";
import { peopleTabsFor } from "@/src/platform/lib/access";
import type { Me } from "@/src/platform/lib/types";

/** People & access: users, roles and teams, one tab each. A tab shows only to a role that may open it. */
export function PeopleTabs({ me, current }: { me: Me; current: "/admin/users" | "/admin/roles" | "/admin/teams" }) {
  const tabs = peopleTabsFor(me);
  if (tabs.length < 2) return null;
  return (
    <nav aria-label="People & access" className="mb-5 flex flex-wrap gap-x-6 gap-y-1 border-b border-rule">
      {tabs.map((t) => (
        <Link
          key={t.href}
          href={t.href}
          aria-current={t.href === current ? "page" : undefined}
          className={`-mb-px border-b-2 px-1 pb-2 text-sm ${t.href === current ? "border-hema font-semibold text-hema" : "border-transparent text-ink-2 hover:text-ink"}`}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
