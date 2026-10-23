"use client";

import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { toast } from "sonner";
import { AsyncButton } from "@/src/modules/inventory/platform/ui/async-button";
import { ConfirmButton } from "@/src/modules/inventory/platform/ui/confirm";

type Outcome = { ok: true; data: unknown } | { ok: false; error: string };

/**
 * One step of a document (place the order, approve, dispatch...): runs it,
 * says how it went, and shows the page as it now stands. Steps that can't be
 * taken back ask first.
 */
export function StepButton({
  run,
  label,
  done,
  variant = "default",
  icon,
  confirm,
  then,
  size = "md",
}: {
  run: () => Promise<Outcome>;
  label: string;
  /** What the toast says when it worked. */
  done: string;
  variant?: "primary" | "default" | "quiet" | "danger";
  icon?: ReactNode;
  /** Ask first, with this title and body. */
  confirm?: { title: string; body?: ReactNode; label?: string; danger?: boolean };
  /** Where to go afterwards, instead of staying. */
  then?: string;
  size?: "md" | "sm";
}) {
  const router = useRouter();

  async function go(): Promise<boolean> {
    const result = await run();
    if (!result.ok) {
      toast.error(result.error);
      return false;
    }
    toast.success(done);
    if (then) router.push(then);
    else router.refresh();
    return true;
  }

  if (confirm) {
    return (
      <ConfirmButton
        label={label}
        icon={icon}
        triggerVariant={variant}
        triggerSize={size}
        title={confirm.title}
        body={confirm.body}
        confirmLabel={confirm.label ?? label}
        danger={confirm.danger ?? variant === "danger"}
        onConfirm={go}
      />
    );
  }
  return (
    <AsyncButton variant={variant} size={size} icon={icon} onRun={async () => void (await go())}>
      {label}
    </AsyncButton>
  );
}
