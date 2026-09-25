"use client";

import { Plus, X } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/**
 * "+ Add …" beside a field whose list is missing what's needed: it opens a
 * small form in a popup, and whatever is made there is picked in the field,
 * so the form being filled in isn't left (or lost).
 *
 * The popup is drawn outside the page's own form (a form can't hold another),
 * so its own button saves it, not the form behind it.
 */
export function QuickAdd({ label, title, children }: { label: string; title: string; children: (done: () => void) => ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const close = () => {
    dialog.current?.close();
    setOpen(false);
  };
  useEffect(() => {
    if (open) dialog.current?.showModal();
  }, [open]);

  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="mt-1 inline-flex items-center gap-1 text-meta font-semibold text-hema hover:underline">
        <Plus className="size-3.5" aria-hidden />
        {label}
      </button>
      {mounted &&
        open &&
        createPortal(
          <dialog
            ref={dialog}
            aria-labelledby={titleId}
            onClose={() => setOpen(false)}
            className="m-auto w-[min(26rem,calc(100vw-2rem))] rounded-[3px] bg-sheet p-0 text-ink shadow-overlay backdrop:bg-ink/30"
          >
            <div className="flex items-center justify-between border-b border-rule px-5 py-3">
              <h2 id={titleId} className="text-heading">
                {title}
              </h2>
              <button type="button" onClick={close} className="rounded-[3px] p-1 text-ink-3 hover:bg-bench hover:text-ink" aria-label="Close">
                <X className="size-4" aria-hidden />
              </button>
            </div>
            <div className="px-5 pt-4 pb-5">{children(close)}</div>
          </dialog>,
          document.body,
        )}
    </>
  );
}
