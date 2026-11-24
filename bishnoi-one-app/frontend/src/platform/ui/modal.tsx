"use client";

import { cn } from "cn";
import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/src/components/ui/dialog";
import { Button } from "./ant-button";

/**
 * Every dialog: shadcn/ui's Dialog, as Studio Admin uses it (2026-11-19), taking the props the screens passed to
 * Ant Design's Modal, so each screen only changes its import. Title top left, close top right, Cancel and the
 * main action at the bottom right (`footer` replaces them; `null` leaves them out).
 */
export type ModalProps = {
  open?: boolean;
  title?: ReactNode;
  children?: ReactNode;
  onCancel?: () => void;
  onOk?: () => unknown;
  okText?: ReactNode;
  cancelText?: ReactNode;
  confirmLoading?: boolean;
  okButtonProps?: { danger?: boolean; disabled?: boolean; loading?: boolean };
  cancelButtonProps?: { disabled?: boolean };
  /** Called once it has opened (true) or closed (false). */
  afterOpenChange?: (open: boolean) => void;
  footer?: ReactNode | null;
  width?: number | string;
  className?: string;
  style?: CSSProperties;
  styles?: { body?: CSSProperties; container?: CSSProperties; mask?: CSSProperties };
  closable?: boolean;
  /** Ant's: false, or { closable: false }, keeps a click outside from closing it. */
  mask?: boolean | { closable?: boolean };
  maskClosable?: boolean;
  keyboard?: boolean;
  centered?: boolean;
  destroyOnHidden?: boolean;
};

function widthOf(width: ModalProps["width"]): CSSProperties | undefined {
  if (width == null) return undefined;
  const w = typeof width === "number" ? `${width}px` : width;
  return { width: `min(${w}, calc(100% - 2rem))`, maxWidth: "none" };
}

export function Modal({
  open = false,
  title,
  children,
  onCancel,
  onOk,
  okText = "OK",
  cancelText = "Cancel",
  confirmLoading,
  okButtonProps,
  cancelButtonProps,
  afterOpenChange,
  footer,
  width,
  className,
  style,
  styles,
  closable = true,
  mask,
  maskClosable,
  keyboard = true,
}: ModalProps) {
  useEffect(() => {
    afterOpenChange?.(open);
    // Only when it opens or closes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  const outsideCloses = maskClosable !== false && !(typeof mask === "object" && mask.closable === false);
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onCancel?.()}>
      <DialogContent
        showCloseButton={closable}
        className={cn("max-h-[calc(100dvh-2rem)] overflow-y-auto", width == null && "sm:max-w-lg", className)}
        style={{ ...widthOf(width), ...style, ...styles?.container }}
        onEscapeKeyDown={keyboard ? undefined : (e) => e.preventDefault()}
        onInteractOutside={outsideCloses ? undefined : (e) => e.preventDefault()}
      >
        {title != null ? (
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
        ) : (
          <DialogTitle className="sr-only">Dialog</DialogTitle>
        )}
        <div style={styles?.body}>{children}</div>
        {footer === undefined ? (
          <DialogFooter>
            <Button onClick={() => onCancel?.()} disabled={confirmLoading || cancelButtonProps?.disabled}>
              {cancelText}
            </Button>
            <Button
              variant={okButtonProps?.danger ? "danger" : "primary"}
              loading={confirmLoading || okButtonProps?.loading}
              disabled={okButtonProps?.disabled}
              onClick={() => onOk?.()}
            >
              {okText}
            </Button>
          </DialogFooter>
        ) : footer !== null ? (
          <DialogFooter>{footer}</DialogFooter>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

type QuickProps = {
  title?: ReactNode;
  content?: ReactNode;
  icon?: ReactNode;
  okText?: ReactNode;
  cancelText?: ReactNode;
  okButtonProps?: { danger?: boolean; disabled?: boolean };
  onOk?: () => unknown;
  onCancel?: () => void;
  width?: number | string;
};

/** A question or a message on its own (Ant's Modal.confirm / Modal.info): waits for onOk if it returns a promise. */
function Quick({ kind, props, close }: { kind: "confirm" | "info"; props: QuickProps; close: () => void }) {
  const [open, setOpen] = useState(true);
  const [busy, setBusy] = useState(false);
  const done = () => {
    setOpen(false);
    setTimeout(close, 200);
  };
  async function ok() {
    try {
      setBusy(true);
      await props.onOk?.();
      done();
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} onOpenChange={(o) => !o && (props.onCancel?.(), done())}>
      <DialogContent showCloseButton={false} className={cn(props.width == null && "sm:max-w-md")} style={widthOf(props.width)}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {props.icon}
            {props.title}
          </DialogTitle>
          {typeof props.content === "string" ? <DialogDescription>{props.content}</DialogDescription> : null}
        </DialogHeader>
        {props.content != null && typeof props.content !== "string" ? <div>{props.content}</div> : null}
        <DialogFooter>
          {kind === "confirm" && (
            <Button onClick={() => (props.onCancel?.(), done())} disabled={busy}>
              {props.cancelText ?? "Cancel"}
            </Button>
          )}
          <Button variant={props.okButtonProps?.danger ? "danger" : "primary"} loading={busy} disabled={props.okButtonProps?.disabled} onClick={ok}>
            {props.okText ?? "OK"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function show(kind: "confirm" | "info", props: QuickProps) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const close = () => {
    root.unmount();
    host.remove();
  };
  root.render(<Quick kind={kind} props={props} close={close} />);
  return { destroy: close };
}

Modal.confirm = (props: QuickProps) => show("confirm", props);
Modal.info = (props: QuickProps) => show("info", props);
Modal.useModal = () => [{ confirm: Modal.confirm, info: Modal.info }, null] as const;
