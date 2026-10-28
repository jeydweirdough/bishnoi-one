import { AboutTip, plainText } from "@/src/platform/ui/about-tip";
import { ArrowDownToLine as Inbound, ChevronRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Icon, type IconName } from "./icons";
import { EmptyDrawing } from "./empty-drawings";

export type Crumb = { href: string; label: string };

/** A white sheet on the bench. The only thing that lifts. */
export function Sheet({ children, className = "", as: Tag = "section", id }: { children: ReactNode; className?: string; as?: "section" | "div" | "article"; /** To link to it (#lines). */ id?: string }) {
  return <Tag id={id} className={`rounded-xl border border-rule bg-sheet shadow-sheet ${className}`}>{children}</Tag>;
}

/** A sheet's heading. Every sheet gets one, in the same style, so sections are found at a glance. */
export function SectionTitle({ children, action, id, icon }: { children: ReactNode; action?: ReactNode; id?: string; icon?: IconName }) {
  return (
    <div className="flex min-h-8 flex-wrap items-center justify-between gap-x-3 gap-y-2">
      {/* The heading keeps its width; in a narrow sheet the action drops below it. */}
      <h2 id={id} className="flex max-w-full shrink-0 items-center gap-2 text-heading text-ink">
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
                  <Link href={c.href} className="text-ink-2 underline-offset-2 hover:text-ink hover:underline">
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
            <AboutTip>{children}</AboutTip>
            <div className="flex items-center">{tools}</div>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <h1 className="text-title text-ink">{title}</h1>
            <AboutTip>{children}</AboutTip>
          </div>
        )}
        {children && !plainText(children) && <div className="mt-1.5 text-ink-2">{children}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/**
 * Nothing here yet, and (`actions`) what to do about it: only what this person may do.
 * As on the components page: a drawing of the kind of thing that's missing (by `icon`),
 * a bold title, one short line, and the first action solid (the next step).
 * `compact`: inside a small card (a chart with no data yet), no actions.
 */
export function Empty({
  title,
  children,
  icon = "inbox",
  actions,
  compact = false,
  art,
  source,
}: {
  title: string;
  children?: ReactNode;
  icon?: IconName;
  actions?: ReactNode;
  compact?: boolean;
  /** A drawing of its own, when the icon's isn't the right one (gauge, steps, flag). */
  art?: string;
  /** Where its items come from, when another app or other people send them ("Executive Admin, when its team…"),
   *  so nobody wonders whom it waits on. A small line at the foot. */
  source?: ReactNode;
}) {
  return (
    <div className={compact ? "px-3 py-4 text-center" : "px-5 py-10 text-center"}>
      <EmptyDrawing icon={art ?? icon} className={`mx-auto ${compact ? "h-[70px] w-[92px]" : "h-[92px] w-[120px]"}`} />
      <p className={`${compact ? "mt-2 text-sm" : "mt-3 text-base"} font-semibold text-ink`}>{title}</p>
      {children && <div className={`mx-auto mt-1 max-w-sm text-ink-3 ${compact ? "text-meta" : "text-sm"}`}>{children}</div>}
      {actions && !compact && (
        // The first action is the next step: solid, whatever the screen passed.
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2 empty:hidden [&>.ant-btn:first-child]:!border-ink [&>.ant-btn:first-child]:!bg-ink [&>.ant-btn:first-child]:!text-white [&>:first-child_.ant-btn]:!border-ink [&>:first-child_.ant-btn]:!bg-ink [&>:first-child_.ant-btn]:!text-white">
          {actions}
        </div>
      )}
      {source && (
        <p className={`mx-auto flex max-w-md items-start justify-center gap-1.5 border-t border-rule text-left text-ink-3 ${compact ? "mt-3 pt-2 text-stamp" : "mt-6 pt-3 text-meta"}`}>
          <Inbound className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>
            <span className="font-medium text-ink-2">Comes from: </span>
            {source}
          </span>
        </p>
      )}
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
