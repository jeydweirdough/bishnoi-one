"use client";

import { UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

// A module's own actions at the top of its pages in the one app (decided
// 2026-10-23): its bell, if it has one, and its page for you (your profile in
// that module). Who you are, the other modules and signing out are in the one
// app's bar above.
export function ModuleActions({ bell, profileHref, profileLabel = "Your profile", children }: { bell?: ReactNode; profileHref?: string; profileLabel?: string; children?: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="flex items-center gap-1">
      {bell}
      {profileHref && (
        <Link
          href={profileHref}
          aria-label={profileLabel}
          title={profileLabel}
          className={`grid size-10 place-items-center rounded-lg text-ink-2 transition-colors hover:bg-sheet hover:text-ink ${pathname === profileHref || pathname.startsWith(`${profileHref}/`) ? "bg-sheet text-ink" : ""}`}
        >
          <UserRound className="size-5" aria-hidden />
        </Link>
      )}
      {children}
    </div>
  );
}
