"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "@/src/platform/ui/icons";

export type ConsoleGroup = { label: string; pages: { href: string; label: string; icon: IconName }[] };

const within = (pathname: string, href: string) => pathname === href || pathname.startsWith(`${href}/`);

/** The Admin Console's pages, by group, as every module's sidebar lists its own. */
export function ConsoleNav({ groups }: { groups: ConsoleGroup[] }) {
  const pathname = usePathname();
  // The most specific page that fits is the current one (Roles vs Role assignments).
  const current = groups
    .flatMap((g) => g.pages)
    .filter((p) => within(pathname, p.href))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;
  return (
    <nav aria-label="Admin Console" className="space-y-5">
      {groups.map((g) => (
        <div key={g.label}>
          <p className="mb-1 px-3 text-caps text-ink-3 uppercase">{g.label}</p>
          <ul className="space-y-0.5">
            {g.pages.map((p) => (
              <li key={p.href}>
                <Link
                  href={p.href}
                  aria-current={p.href === current ? "page" : undefined}
                  className={`flex h-9 items-center gap-2.5 rounded-[3px] px-3 text-sm ${
                    p.href === current ? "bg-hema-tint font-semibold text-hema" : "text-ink-2 hover:bg-sheet hover:text-ink"
                  }`}
                >
                  <Icon name={p.icon} className="size-[1.125rem]" />
                  {p.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}
