"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Button } from "@/src/modules/console/platform/ui/button";

// A button that opens a form in a panel over the page, so a page isn't half
// form before anyone needs one. The form is made fresh each time it opens.
// Used across the Service screens (applications, incidents, support).

type Props = {
  /** What the button says; for an icon-only tool, what it does (read aloud and as its tooltip). */
  label: string;
  /** The panel's heading. */
  title: string;
  icon?: ReactNode;
  variant?: "primary" | "default" | "quiet";
  size?: "md" | "sm";
  /** Draw the trigger as a small icon beside the thing it acts on. */
  tool?: boolean;
  wide?: boolean;
  children: (close: () => void) => ReactNode;
};

export const TOOL = "inline-flex size-8 shrink-0 items-center justify-center rounded-full text-ink-3 transition-colors hover:bg-hema-tint hover:text-hema";

export function PanelButton({ label, title, icon, variant = "default", size = "md", tool = false, wide = false, children }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const titleId = useId();

  useEffect(() => {
    if (open) dialog.current?.showModal();
  }, [open]);

  const close = () => dialog.current?.close();

  return (
    <>
      {tool ? (
        <button suppressHydrationWarning type="button" onClick={() => setOpen(true)} aria-label={label} title={label} aria-haspopup="dialog" className={TOOL}>
          {icon}
        </button>
      ) : (
        <Button variant={variant} size={size} icon={icon} onClick={() => setOpen(true)} aria-haspopup="dialog">
          {label}
        </Button>
      )}
      {open && (
        <dialog
          ref={dialog}
          onClose={() => setOpen(false)}
          aria-labelledby={titleId}
          className={`m-auto ${wide ? "w-[min(40rem,calc(100vw-2rem))]" : "w-[min(30rem,calc(100vw-2rem))]"} rounded-[22px] bg-sheet p-0 text-left text-ink shadow-overlay backdrop:bg-ink/30`}
        >
          <div className="flex items-center justify-between gap-3 border-b border-rule px-5 py-3">
            <h2 id={titleId} className="text-heading">
              {title}
            </h2>
            <button suppressHydrationWarning type="button" onClick={close} className="rounded-full p-1 text-ink-3 hover:bg-bench hover:text-ink" aria-label="Close">
              <X className="size-4" aria-hidden />
            </button>
          </div>
          <div className="max-h-[75vh] overflow-y-auto px-5 pt-4 pb-5">{children(close)}</div>
        </dialog>
      )}
    </>
  );
}

/** The Save / Cancel row every panel form ends with. */
export function PanelActions({ pending, save, onCancel }: { pending: boolean; save: string; onCancel: () => void }) {
  return (
    <div className="flex flex-wrap gap-2 pt-1">
      <Button type="submit" variant="primary" loading={pending}>
        {save}
      </Button>
      <Button variant="quiet" onClick={onCancel} disabled={pending}>
        Cancel
      </Button>
    </div>
  );
}
