import { ChevronRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Icon, type IconName } from "./icons";

export type Crumb = { href: string; label: string };

/** A white sheet on the bench. The only thing that lifts. */
export function Sheet({ children, className = "", as: Tag = "section" }: { children: ReactNode; className?: string; as?: "section" | "div" | "article" }) {
  return <Tag className={`rounded-[3px] bg-sheet shadow-sheet ${className}`}>{children}</Tag>;
}

/** A sheet's heading. Every sheet gets one, in the same style, so sections are found at a glance. */
export function SectionTitle({ children, action, id, icon }: { children: ReactNode; action?: ReactNode; id?: string; icon?: IconName }) {
  return (
    <div className="flex min-h-8 items-center justify-between gap-3">
      <h2 id={id} className="flex min-w-0 items-center gap-2 text-heading text-ink">
        {icon && <Icon name={icon} className="size-[1.125rem] text-ink-3" />}
        <span className="min-w-0">{children}</span>
      </h2>
      {action}
    </div>
  );
}

/** A part within a sheet (Notes under Particulars): one step below the sheet's heading. */
export function Subheading({ children }: { children: ReactNode }) {
  return <h3 className="text-sm font-semibold text-ink">{children}</h3>;
}

/**
 * A page's title, what it's about, and its actions. Pages below a list get
 * breadcrumbs back up the path (the way every web app does it); a list page's
 * place is already shown in the sidebar, so it gets none.
 */
export function PageHeader({
  title,
  crumbs,
  children,
  actions,
  tools,
}: {
  title: ReactNode;
  crumbs?: Crumb[];
  children?: ReactNode;
  actions?: ReactNode;
  /** Small icon buttons that act on what the title names (edit it, delete it), drawn beside it. */
  tools?: ReactNode;
}) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        {crumbs && crumbs.length > 0 && (
          <nav aria-label="Breadcrumb" className="mb-1">
            <ol className="flex flex-wrap items-center gap-1 text-meta">
              {crumbs.map((c, i) => (
                <li key={c.href} className="inline-flex items-center gap-1">
                  {i > 0 && <ChevronRight className="size-3.5 text-ink-3" aria-hidden />}
                  <Link href={c.href} className="text-ink-2 underline-offset-2 hover:text-hema hover:underline">
                    {c.label}
                  </Link>
                </li>
              ))}
            </ol>
          </nav>
        )}
        {tools ? (
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <h1 className="text-title text-ink">{title}</h1>
            <div className="flex items-center">{tools}</div>
          </div>
        ) : (
          <h1 className="text-title text-ink">
            {title}
          </h1>
        )}
        {children && <div className="mt-1.5 text-ink-2">{children}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/** Nothing here yet, and (`actions`) what to do about it: only what this person may do. */
export function Empty({ title, children, icon = "inbox", actions }: { title: string; children?: ReactNode; icon?: IconName; actions?: ReactNode }) {
  return (
    <div className="px-5 py-10 text-center">
      <span className="mx-auto mb-3 flex size-10 items-center justify-center rounded-full bg-bench text-ink-3">
        <Icon name={icon} className="size-5" />
      </span>
      <p className="font-semibold text-ink-2">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-md text-meta text-ink-3">{children}</div>}
      {actions && <div className="mt-4 flex flex-wrap items-center justify-center gap-2 empty:hidden">{actions}</div>}
    </div>
  );
}

/** Label / value pairs, the way a record sheet lists particulars. */
export function Particulars({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[minmax(6.5rem,auto)_1fr] gap-x-5 gap-y-2.5 text-sm">
      {items.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-ink-3">{label}</dt>
          <dd className="min-w-0 break-words text-ink">{value ?? <span className="text-ink-3">—</span>}</dd>
        </div>
      ))}
    </dl>
  );
}
