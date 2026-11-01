"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { currentOf, type Step } from "@/src/platform/shell/sidebar";

export type LinkTab = Pick<Step, "href" | "label" | "also" | "exact">;

/**
 * Tabs whose every tab is a page (2026-11-01): the parts of one area of settings (an app's categories, brands,
 * units…) side by side instead of a sidebar row each. Each tab is a real link, so the address names the tab,
 * Back goes to the tab before, and old links keep working. The tab you're on is the most specific match, as in
 * the sidebar. `sub`: a second, smaller row under the first, for an area whose tabs have pages of their own.
 */
export function LinkTabs({ tabs, label, sub = false }: { tabs: LinkTab[]; label: string; sub?: boolean }) {
  const pathname = usePathname();
  const here = currentOf(tabs, pathname, null);
  if (tabs.length < 2) return null;
  return (
    <nav aria-label={label} className={sub ? "mb-5 -mt-1" : "mb-5 border-b border-rule"}>
      <ul className={`-mb-px flex overflow-x-auto ${sub ? "gap-1" : "gap-6"}`}>
        {tabs.map((t) => {
          const on = t === here;
          return (
            <li key={t.href} className="shrink-0">
              {sub ? (
                <Link
                  href={t.href}
                  aria-current={on ? "page" : undefined}
                  className={`inline-flex h-9 items-center rounded-full px-3.5 text-sm whitespace-nowrap transition-colors ${on ? "bg-ink font-medium text-white" : "text-ink-2 hover:bg-rule hover:text-ink"}`}
                >
                  {t.label}
                </Link>
              ) : (
                <Link
                  href={t.href}
                  aria-current={on ? "page" : undefined}
                  className={`inline-flex h-11 items-center border-b-2 text-sm whitespace-nowrap transition-colors ${on ? "border-ink font-semibold text-ink" : "border-transparent text-ink-2 hover:border-rule-strong hover:text-ink"}`}
                >
                  {t.label}
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
