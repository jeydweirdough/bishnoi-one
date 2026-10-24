import Link from "next/link";

/**
 * The top of a module's sidebar, as before the one app: the Bishnoi One mark,
 * which module this is (the mark says Bishnoi One), and the company you're working in. One component for
 * every module's sidebar (decided 2026-10-24), so they read the same.
 */
export function ModuleBrand({ href, label, company }: { href: string; label: string; company?: string | null }) {
  return (
    <Link href={href} className="flex items-center gap-2.5 border-b border-rule pb-4">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/brand/bishnoi-one-mark.png" alt="" width={36} height={36} className="size-9 shrink-0" />
      <span className="min-w-0">
        <span className="block truncate text-sm leading-tight font-semibold text-ink">{label}</span>
        {company && <span className="block truncate text-meta text-ink-3">{company}</span>}
      </span>
    </Link>
  );
}
