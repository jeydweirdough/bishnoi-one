"use client";

import { Modal } from "antd";
import { TriangleAlert } from "lucide-react";
import { useState, useTransition, type ReactNode } from "react";
import { Field, FormError, Input } from "./field";

type Props = {
  open: boolean;
  onClose: () => void;
  /** "Delete employee permanently". */
  title: string;
  /** What will be lost. */
  children: ReactNode;
  /** What they type to show they mean this one: the email, the name. */
  name: string;
  nameLabel: string;
  /** The second thing they type: "delete employee". */
  phrase: string;
  /** The button. */
  action: string;
  onConfirm: () => Promise<{ ok: true } | { ok: false; error: string }>;
};

/**
 * Deleting what can't be brought back, as Vercel asks it (2026-11-01): what will be lost, then type its name and a
 * phrase; the red button opens only when both match, so a slip of the hand can't do it.
 */
export function TypeToDelete({ open, onClose, title, children, name, nameLabel, phrase, action, onConfirm }: Props) {
  const [typedName, setTypedName] = useState("");
  const [typedPhrase, setTypedPhrase] = useState("");
  const [error, setError] = useState<string>();
  const [busy, start] = useTransition();
  const matches = typedName.trim().toLowerCase() === name.toLowerCase() && typedPhrase.trim().toLowerCase() === phrase.toLowerCase();

  function close() {
    if (busy) return;
    setTypedName("");
    setTypedPhrase("");
    setError(undefined);
    onClose();
  }

  return (
    <Modal
      open={open}
      title={title}
      onCancel={close}
      onOk={() =>
        start(async () => {
          const r = await onConfirm();
          if (r.ok) close();
          else setError(r.error);
        })
      }
      okText={action}
      okButtonProps={{ danger: true, disabled: !matches }}
      confirmLoading={busy}
      width={500}
      destroyOnHidden
    >
      <div className="space-y-4 pt-2">
        <div className="text-sm text-ink-2">{children}</div>
        <p role="alert" className="flex items-center gap-2 rounded-lg bg-danger-tint px-3 py-2 text-sm font-medium text-danger">
          <TriangleAlert className="size-4 shrink-0" aria-hidden />
          This can&apos;t be undone.
        </p>
        <Field
          label={
            <>
              {nameLabel}: <span className="font-semibold">{name}</span>
            </>
          }
        >
          {(p) => <Input {...p} value={typedName} onChange={(e) => setTypedName(e.target.value)} autoComplete="off" spellCheck={false} autoFocus />}
        </Field>
        <Field
          label={
            <>
              To verify, type <span className="font-semibold">{phrase}</span>
            </>
          }
        >
          {(p) => <Input {...p} value={typedPhrase} onChange={(e) => setTypedPhrase(e.target.value)} autoComplete="off" spellCheck={false} />}
        </Field>
        <FormError message={error} />
      </div>
    </Modal>
  );
}
