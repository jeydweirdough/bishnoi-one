"use client";

import { Popover } from "antd";
import { Bell, Mail, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, use, useState } from "react";

// The CRM's own actions at the top of its pages, in the one app: its search,
// its notification bell (the attention prompts) and its own pages for you (your
// CRM profile, your mailbox). Who you are, the other modules and signing out
// are in the one app's bar above (decided 2026-10-23).

/** One notification: what, why, and where it's dealt with. */
export type Notification = { key: string; title: string; reason?: string; href: string };

export function TopActions({ notifications, allHref, search }: { notifications?: Promise<Notification[]>; allHref?: string; search?: React.ReactNode }) {
  const pathname = usePathname();
  const iconLink = (href: string, label: string, icon: React.ReactNode) => (
    <Link
      href={href}
      aria-label={label}
      title={label}
      className={`grid size-10 place-items-center rounded-lg text-ink-2 transition-colors hover:bg-sheet hover:text-ink ${pathname === href ? "bg-sheet text-ink" : ""}`}
    >
      {icon}
    </Link>
  );
  return (
    <div className="flex items-center gap-1">
      {search}
      {notifications && (
        <Suspense fallback={<BellButton count={0} />}>
          <LoadedBell notifications={notifications} allHref={allHref} />
        </Suspense>
      )}
      {iconLink("/crm/account/mailbox", "Your mailbox", <Mail className="size-5" aria-hidden />)}
      {iconLink("/crm/account", "Your CRM profile", <UserRound className="size-5" aria-hidden />)}
    </div>
  );
}

function BellButton({ count, open = false }: { count: number; open?: boolean }) {
  return (
    <button
      type="button"
      aria-label={count ? `Notifications: ${count}` : "Notifications"}
      title="Notifications"
      className={`relative grid size-10 place-items-center rounded-lg text-ink-2 transition-colors hover:bg-sheet hover:text-ink ${open ? "bg-sheet text-ink" : ""}`}
    >
      <Bell className="size-5" aria-hidden />
      {count > 0 && (
        <span className="absolute top-1 right-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[0.625rem] leading-none font-semibold text-white tabular-nums ring-2 ring-bench" aria-hidden>
          {count > 9 ? "9+" : count}
        </span>
      )}
    </button>
  );
}

function LoadedBell({ notifications, allHref }: { notifications: Promise<Notification[]>; allHref?: string }) {
  const items = use(notifications);
  const pathname = usePathname();
  // The list belongs to the page it was opened on, so navigating closes it.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = openOn === pathname;
  const close = () => setOpenOn(null);
  const list = (
    <div className="w-[min(22rem,calc(100vw-2rem))]">
      <div className="flex items-center justify-between gap-3 border-b border-rule px-4 py-3">
        <p className="font-semibold text-ink">Notifications</p>
        {allHref && items.length > 0 && (
          <Link href={allHref} onClick={close} className="text-meta font-medium text-ink hover:underline">
            See all
          </Link>
        )}
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-8 text-center">
          <Bell className="mx-auto size-6 text-ink-3" aria-hidden />
          <p className="mt-2 text-sm font-semibold text-ink">No pending items</p>
          <p className="mt-0.5 text-meta text-ink-3">Overdue follow-ups, pending quotes and similar items appear here.</p>
        </div>
      ) : (
        <ul className="max-h-[min(24rem,60dvh)] divide-y divide-rule overflow-y-auto">
          {items.map((n) => (
            <li key={n.key}>
              <Link href={n.href} onClick={close} className="block px-4 py-3 hover:bg-sheet">
                <span className="block text-sm font-semibold text-ink">{n.title}</span>
                {n.reason && <span className="mt-0.5 block text-meta text-ink-3">{n.reason}</span>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
  return (
    <Popover content={list} trigger="click" placement="bottomRight" arrow={false} open={open} onOpenChange={(o) => setOpenOn(o ? pathname : null)} styles={{ container: { padding: 0 } }}>
      <span className="inline-flex">
        <BellButton count={items.length} open={open} />
      </span>
    </Popover>
  );
}
