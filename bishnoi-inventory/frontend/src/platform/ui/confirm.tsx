"use client";

import { Modal } from "antd";
import { useState, useTransition, type ReactNode } from "react";
import { Button } from "./button";

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
  const [open, setOpen] = useState(false);
  const [pending, start] = useTransition();

  function confirm() {
    start(async () => {
      const outcome = await onConfirm().catch(() => false);
      if (outcome !== false) setOpen(false);
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
        onClick={() => setOpen(true)}
        disabled={disabled}
        aria-haspopup="dialog"
      >
        {label}
      </Button>
      {/* Ant Design's modal: it can't be closed while the action runs. */}
      <Modal
        open={open}
        title={title}
        onCancel={() => !pending && setOpen(false)}
        onOk={confirm}
        okText={confirmLabel}
        cancelText="Cancel"
        confirmLoading={pending}
        okButtonProps={{ danger }}
        cancelButtonProps={{ disabled: pending }}
        closable={!pending}
        mask={{ closable: !pending }}
        width={420}
        destroyOnHidden
      >
        {body && <div className="text-sm text-ink-2">{body}</div>}
      </Modal>
    </>
  );
}
