import Link from "next/link";

/** A customer's record: its activity and its quotes, in one card, one tab showing at a time. */
export function RecordTabs({ base, current, tabs }: { base: string; current: string; tabs: { key: string; label: string; count?: number }[] }) {
  return (
    <nav aria-label="Record" className="-mx-5 mb-1 flex gap-6 border-b border-rule px-5">
      {tabs.map((t) => (
        <Link
          key={t.key}
          href={t.key === tabs[0].key ? base : `${base}?tab=${t.key}`}
          scroll={false}
          aria-current={t.key === current ? "page" : undefined}
          className={`-mb-px border-b-2 pt-3 pb-2 text-sm ${t.key === current ? "border-hema font-semibold text-hema" : "border-transparent text-ink-2 hover:text-ink"}`}
        >
          {t.label}
          {t.count ? <span className="ml-1 text-meta font-normal text-ink-3">{t.count}</span> : null}
        </Link>
      ))}
    </nav>
  );
}
