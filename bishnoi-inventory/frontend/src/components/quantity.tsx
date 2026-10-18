"use client";

import { useEffect, useRef, useState } from "react";
import { CellInput } from "@/src/platform/ui/field";

/**
 * A quantity that knows how much there is. Typed past the most there is (only
 * 40 available, 50 typed), it shakes, sets itself to the most, and says so
 * under it for a moment: the line can't be saved for more than can be given.
 * With no limit (stock coming in), it's a plain whole number.
 *
 * `max` is the most allowed; `min` the least (an adjustment that removes
 * stock can't take more than is on hand: -onHand). Either may be left out.
 */
export function QuantityInput({
  value,
  onChange,
  max,
  min,
  unit,
  label,
  signed = false,
  className = "w-20",
  invalid,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  max?: number;
  min?: number;
  unit?: string;
  label: string;
  /** Allows a minus (adjustments that may add or remove). */
  signed?: boolean;
  className?: string;
  invalid?: boolean;
  placeholder?: string;
}) {
  const [shaking, setShaking] = useState(false);
  const [said, setSaid] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), []);

  function warn(text: string) {
    setShaking(false);
    // Restart the shake on every overrun, even twice in a row.
    requestAnimationFrame(() => setShaking(true));
    setSaid(text);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setSaid(null), 3500);
  }

  function change(raw: string) {
    const clean = raw.replace(signed ? /[^\d-]/g : /\D/g, "").replace(/(?!^)-/g, "");
    const n = Number(clean);
    if (clean === "" || clean === "-" || Number.isNaN(n)) return onChange(clean);
    if (max !== undefined && n > max) {
      warn(max <= 0 ? `None available${unit ? ` (${unit})` : ""}` : `Only ${max.toLocaleString()}${unit ? ` ${unit}` : ""} available; set to ${max.toLocaleString()}`);
      return onChange(String(Math.max(0, max)));
    }
    if (min !== undefined && n < min) {
      warn(`Only ${Math.abs(min).toLocaleString()}${unit ? ` ${unit}` : ""} on hand; set to ${min.toLocaleString()}`);
      return onChange(String(min));
    }
    onChange(clean);
  }

  return (
    <span className="relative inline-block">
      <CellInput
        aria-label={label}
        aria-invalid={invalid || shaking || undefined}
        inputMode={signed ? "text" : "numeric"}
        placeholder={placeholder}
        value={value}
        onChange={(e) => change(e.target.value)}
        onAnimationEnd={() => setShaking(false)}
        className={`${className} ${shaking ? "animate-shake !border-danger" : ""}`}
      />
      <span aria-live="polite" className="sr-only">
        {said}
      </span>
      {said && (
        <span className="absolute top-full right-0 z-10 mt-1 w-max max-w-56 rounded-md bg-ink px-2.5 py-1 text-[0.6875rem] leading-snug text-white shadow-overlay" aria-hidden>
          {said}
        </span>
      )}
    </span>
  );
}
