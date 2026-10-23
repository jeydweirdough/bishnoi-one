"use client";

import { useTransition, type ComponentProps } from "react";
import { Button, Spinner } from "@/src/modules/console/platform/ui/button";

/** A button whose click runs async work, showing a spinner and blocking repeat clicks until it's done. */
export function AsyncButton({ onRun, ...rest }: Omit<ComponentProps<typeof Button>, "onClick" | "loading"> & { onRun: () => Promise<void> }) {
  const [pending, start] = useTransition();
  return <Button {...rest} loading={pending} onClick={() => start(onRun)} />;
}

/** The same, for a bare element styled by the caller (chips, icons). */
export function AsyncChip({
  onRun,
  children,
  className = "",
  ...rest
}: Omit<ComponentProps<"button">, "onClick"> & { onRun: () => Promise<void> }) {
  const [pending, start] = useTransition();
  return (
    <button
      type="button"
      {...rest}
      disabled={pending}
      aria-busy={pending || undefined}
      onClick={() => start(onRun)}
      className={`inline-flex items-center gap-1 disabled:opacity-60 ${className}`}
    >
      {pending && <Spinner className="size-2.5" />}
      {children}
    </button>
  );
}
