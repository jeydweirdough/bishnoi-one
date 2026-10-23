"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { Button } from "@/src/modules/admin/platform/ui/button";

// A dialog drawn while `open`, on the browser's own <dialog> (as ConfirmButton's):
// a title, what's in it, and Cancel and OK at its foot unless `footer` is null.

type Props = {
  open: boolean;
  title: ReactNode;
  children?: ReactNode;
  onCancel: () => void;
  onOk?: () => void;
  okText?: string;
  cancelText?: string;
  confirmLoading?: boolean;
  /** Its widest, in pixels; never wider than the screen. */
  width?: number;
  footer?: null;
};

export function Modal({ open, title, children, onCancel, onOk, okText = "OK", cancelText = "Cancel", confirmLoading = false, width = 520, footer }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    if (open && dialog.current && !dialog.current.open) dialog.current.showModal();
  }, [open]);
  if (!open) return null;
  return (
    <dialog
      ref={dialog}
      aria-labelledby={titleId}
      onCancel={(e) => {
        // Escape asks the screen, which decides (it says no while saving).
        e.preventDefault();
        onCancel();
      }}
      style={{ width: `min(${width}px, calc(100vw - 2rem))` }}
      className="m-auto max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-[3px] bg-sheet p-0 text-ink shadow-overlay"
    >
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <h2 id={titleId} className="text-heading">
            {title}
          </h2>
          <button type="button" onClick={onCancel} aria-label="Close" className="-mt-1 -mr-1 grid size-8 shrink-0 place-items-center rounded-full text-ink-3 hover:bg-bench hover:text-ink">
            <X className="size-4" aria-hidden />
          </button>
        </div>
        {children}
        {footer !== null && (
          <div className="mt-5 flex justify-end gap-2">
            <Button onClick={onCancel} disabled={confirmLoading}>
              {cancelText}
            </Button>
            <Button variant="primary" loading={confirmLoading} onClick={onOk}>
              {okText}
            </Button>
          </div>
        )}
      </div>
    </dialog>
  );
}
