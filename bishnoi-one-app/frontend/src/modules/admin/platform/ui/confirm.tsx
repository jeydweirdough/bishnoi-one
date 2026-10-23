"use client";

import { useId, useRef, useTransition, type ReactNode } from "react";
import { Button } from "@/src/modules/admin/platform/ui/button";

type Props = {
  /** What the trigger button says. */
  label: ReactNode;
  title: string;
  body?: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  triggerVariant?: "primary" | "default" | "quiet" | "danger";
  triggerSize?: "md" | "sm";
  triggerClassName?: string;
  /** The trigger's tooltip, for a trigger that is only an icon. */
  triggerTitle?: string;
  icon?: ReactNode;
  disabled?: boolean;
  /** Return false (or throw) to keep the dialog open, e.g. when the action failed. */
  onConfirm: () => Promise<boolean | void>;
};

/** A button that asks first. Used for anything destructive or hard to undo. */
export function ConfirmButton({
  label,
  title,
  body,
  confirmLabel,
  danger = true,
  triggerVariant = "default",
  triggerSize = "md",
  triggerClassName,
  triggerTitle,
  icon,
  disabled,
  onConfirm,
}: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [pending, start] = useTransition();
  const titleId = useId();

  function show() {
    dialog.current?.showModal();
  }

  function close() {
    if (pending) return;
    dialog.current?.close();
  }

  function confirm() {
    start(async () => {
      const outcome = await onConfirm().catch(() => false);
      if (outcome !== false) dialog.current?.close();
    });
  }

  return (
    <>
      <Button
        variant={triggerVariant}
        size={triggerSize}
        icon={icon}
        className={triggerClassName}
        title={triggerTitle}
        onClick={show}
        disabled={disabled}
        aria-haspopup="dialog"
      >
        {label}
      </Button>
      <dialog
        ref={dialog}
        onCancel={(e) => pending && e.preventDefault()}
        aria-labelledby={titleId}
        className="m-auto w-[min(26rem,calc(100vw-2rem))] rounded-[12px] bg-sheet p-0 text-ink shadow-overlay"
      >
        <div className="p-5">
          <h2 id={titleId} className="text-heading">
            {title}
          </h2>
          {body && <div className="mt-2 text-sm text-ink-2">{body}</div>}
          <div className="mt-5 flex justify-end gap-2">
            <Button onClick={close} disabled={pending} autoFocus>
              Cancel
            </Button>
            <Button variant={danger ? "danger" : "primary"} loading={pending} onClick={confirm}>
              {confirmLabel}
            </Button>
          </div>
        </div>
      </dialog>
    </>
  );
}
