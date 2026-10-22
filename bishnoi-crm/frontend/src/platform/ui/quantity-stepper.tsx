"use client";

import { Minus, Plus } from "lucide-react";
import type { ComponentProps } from "react";

/**
 * A quantity as the UI kit's order card has it: − [20] +. Typed or stepped by
 * one; the field keeps its text, so a half-typed number is left alone.
 */
export function QuantityStepper({
  value,
  onChange,
  min = 1,
  ...rest
}: Omit<ComponentProps<"input">, "value" | "onChange"> & { value: string; onChange: (value: string) => void; min?: number }) {
  const n = /^\d+$/.test(value.trim()) ? Number(value) : null;
  const step = (by: number) => onChange(String(Math.max(min, (n ?? min) + by)));
  const btn = "grid size-8 shrink-0 place-items-center text-ink-2 transition-colors hover:bg-[#f4f4f2] hover:text-ink disabled:opacity-40";
  return (
    <div className="inline-flex h-9 w-full max-w-[8.5rem] items-stretch overflow-hidden rounded-[8px] border border-[#dededa] bg-sheet focus-within:border-ink focus-within:shadow-[0_0_0_3px_rgba(168,214,155,0.45)] aria-invalid:border-danger" aria-invalid={rest["aria-invalid"]}>
      <button type="button" className={btn} onClick={() => step(-1)} disabled={n !== null && n <= min} aria-label="One less" tabIndex={-1}>
        <Minus className="size-3.5" aria-hidden />
      </button>
      <input
        {...rest}
        inputMode="numeric"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "ArrowUp") (e.preventDefault(), step(1));
          if (e.key === "ArrowDown") (e.preventDefault(), step(-1));
          rest.onKeyDown?.(e);
        }}
        className="w-full min-w-0 border-x border-[#ececea] bg-transparent text-center text-sm text-ink tabular-nums outline-none"
      />
      <button type="button" className={btn} onClick={() => step(1)} aria-label="One more" tabIndex={-1}>
        <Plus className="size-3.5" aria-hidden />
      </button>
    </div>
  );
}
