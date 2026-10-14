"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Popover } from "antd";
import { useState } from "react";
import type { Alert } from "../lib/types";
import { AlertList } from "./alerts";

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
            <Link href="/alerts" className="text-meta text-ink hover:underline">
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
        aria-label={any ? `Needs attention: ${alerts.length}` : "Needs attention: none"}
        className="relative inline-flex size-10 items-center justify-center rounded-lg text-ink-2 hover:bg-sheet hover:text-ink"
      >
        <Bell className="size-5" aria-hidden />
        {any && <span className="absolute top-2 right-2.5 size-2 rounded-full bg-danger ring-2 ring-bench" aria-hidden />}
      </button>
    </Popover>
  );
}
