"use client";

import { CircleAlert, X } from "lucide-react";
import { useEffect, useState } from "react";

/**
 * The platform's "no" ("Your Bishnoi One account doesn't include CRM…") as an
 * alert over the page, the same as the apps' (shell/app-launcher.tsx), rather
 * than a page of its own. Closed with ✕, or by itself after 10 seconds.
 */
export function GoNotice({ text }: { text: string }) {
  const [open, setOpen] = useState(true);
  useEffect(() => {
    const t = window.setTimeout(() => setOpen(false), 10_000);
    return () => window.clearTimeout(t);
  }, []);
  if (!open) return null;
  return (
    <div role="alert" className="fixed top-4 left-1/2 z-[60] flex w-[min(28rem,calc(100vw-2rem))] -translate-x-1/2 items-start gap-3 rounded-xl border border-rule bg-sheet px-4 py-3 shadow-lg">
      <CircleAlert className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden />
      <p className="min-w-0 flex-1 text-sm text-ink">{text}</p>
      <button type="button" onClick={() => setOpen(false)} aria-label="Close" className="grid size-6 shrink-0 place-items-center rounded-md text-ink-3 hover:bg-bench hover:text-ink">
        <X className="size-4" aria-hidden />
      </button>
    </div>
  );
}
