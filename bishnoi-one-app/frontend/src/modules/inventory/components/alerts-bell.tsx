"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Popover } from "antd";
import { useState } from "react";
import type { Alert } from "@/src/modules/inventory/lib/types";
import { AlertList } from "@/src/modules/inventory/components/alerts";

/**
 * What needs attention, behind the bell at the top of every page: a small red
 * dot while anything does, and the list when pressed. It belongs to the
 * person, not to Home, so it's there wherever they are.
 */
export function AlertsBell({ alerts }: { alerts: Alert[] }) {
  const pathname = usePathname();
  // Following one of its links is leaving it: it opens again only when asked.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = openOn === pathname;
  const any = alerts.length > 0;
  return (
    <Popover
      open={open}
      onOpenChange={(next) => setOpenOn(next ? pathname : null)}
      trigger="click"
      placement="bottomRight"
      arrow={false}
      content={
        <div className="w-[min(24rem,calc(100vw-2rem))] px-1 py-1">
          <div className="flex items-center justify-between gap-3 px-1">
            <p className="text-sm font-semibold text-ink">Needs attention</p>
            <Link href="/inventory/alerts" className="text-meta text-ink hover:underline">
              All alerts
            </Link>
          </div>
          <div className="max-h-[min(28rem,70dvh)] overflow-y-auto px-1">
            <AlertList alerts={alerts} compact />
          </div>
        </div>
      }
    >
      <button
        type="button"
        title="Notifications"
        aria-label={any ? `Notifications: ${alerts.length}` : "Notifications"}
        className={`relative grid size-10 place-items-center rounded-lg text-ink-2 transition-colors hover:bg-sheet hover:text-ink ${open ? "bg-sheet text-ink" : ""}`}
      >
        <Bell className="size-5" aria-hidden />
        {any && (
          <span className="absolute top-1 right-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[0.625rem] leading-none font-semibold text-white tabular-nums ring-2 ring-bench" aria-hidden>
            {alerts.length > 9 ? "9+" : alerts.length}
          </span>
        )}
      </button>
    </Popover>
  );
}
