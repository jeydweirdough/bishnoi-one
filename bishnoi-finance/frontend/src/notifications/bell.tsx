"use client";

import { Bell as BellIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";
import { loadInbox, markRead } from "./actions";
import type { Inbox, Notice } from "./types";

// Finance's bell, at the top right beside the profile (the shared shell's `bell`
// slot). What's waiting on you, or was done to your work: made by the API as it
// happens (app/notify.py), never for what you did yourself. Planned 2026-10-22.

/** "just now", "5 min ago", "3 h ago", then the date. */
function ago(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 24 * 60) return `${Math.round(minutes / 60)} h ago`;
  return new Date(iso).toLocaleDateString("en-PH", { month: "short", day: "numeric" });
}

/** `unread`: the count the page was drawn with (GET /finance/frame); fetched afresh on opening. */
export function Bell({ unread }: { unread: number }) {
  const pathname = usePathname();
  // Opened on one page; going to another closes it.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = openOn === pathname;
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const box = useRef<HTMLDivElement>(null);
  const count = inbox?.unread ?? unread;

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpenOn(null);
    const escape = (e: KeyboardEvent) => e.key === "Escape" && setOpenOn(null);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  function toggle() {
    if (open) return setOpenOn(null);
    setOpenOn(pathname);
    setError(null);
    start(async () => {
      const r = await loadInbox();
      if (r.ok) setInbox(r.data);
      else setError(r.error);
    });
  }

  function read(ids?: string[]) {
    start(async () => {
      const r = await markRead(ids);
      if (r.ok) setInbox(r.data);
    });
  }

  function opened(n: Notice) {
    setOpenOn(null);
    if (!n.read) read([n.id]);
  }

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={toggle}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={count ? `Notifications: ${count} unread` : "Notifications"}
        title="Notifications"
        className={`relative flex size-10 items-center justify-center rounded-[3px] text-ink-2 transition-colors hover:bg-sheet hover:text-ink ${open ? "bg-hema-tint" : ""}`}
      >
        <BellIcon className="size-5" aria-hidden />
        {count > 0 && (
          <span className="absolute top-1 right-1 min-w-4 rounded-full bg-danger px-1 text-center text-[0.625rem] leading-4 font-semibold text-white tabular-nums">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>
      {open && (
        <div role="dialog" aria-label="Notifications" className="absolute top-full right-0 z-40 mt-1 w-[min(24rem,calc(100vw-2rem))] rounded-[3px] border border-rule bg-sheet shadow-overlay">
          <div className="flex items-center justify-between border-b border-rule px-4 py-2.5">
            <p className="text-sm font-semibold text-ink">Notifications</p>
            {count > 0 && (
              <button type="button" onClick={() => read()} disabled={pending} className="text-meta text-hema hover:underline disabled:opacity-60">
                Mark all as read
              </button>
            )}
          </div>
          {error ? (
            <p className="px-4 py-5 text-meta text-danger">{error}</p>
          ) : !inbox ? (
            <p className="px-4 py-5 text-meta text-ink-3">Loading…</p>
          ) : inbox.items.length === 0 ? (
            <p className="px-4 py-5 text-meta text-ink-3">Nothing yet. What&apos;s waiting on you, and decisions on your work, show here.</p>
          ) : (
            <ul className="max-h-[min(28rem,70dvh)] divide-y divide-rule overflow-y-auto">
              {inbox.items.map((n) => {
                const body = (
                  <>
                    <span className={`block text-sm ${n.read ? "text-ink-2" : "font-semibold text-ink"}`}>{n.text}</span>
                    <span className="mt-0.5 block text-meta text-ink-3">{ago(n.at)}</span>
                  </>
                );
                return (
                  <li key={n.id} className={n.read ? "" : "bg-hema-tint/40"}>
                    {n.link ? (
                      <Link href={n.link} onClick={() => opened(n)} className="block px-4 py-2.5 hover:bg-bench">
                        {body}
                      </Link>
                    ) : (
                      <button type="button" onClick={() => opened(n)} className="block w-full px-4 py-2.5 text-left hover:bg-bench">
                        {body}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
