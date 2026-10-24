"use client";

import { useState, useTransition, useCallback, useRef } from "react";
import { toast } from "sonner";

export type ActionResult<T = unknown> =
  | { ok: true; data: T }
  | { ok: false; error: string; fields?: Record<string, string>; duplicates?: unknown[] };

export type AnticipationOptions<TData, TState> = {
  /** Optimistic update applied immediately to UI state before server request completes */
  anticipate: () => TState;
  /** Rollback function if backend bounces back with an error */
  rollback: (previous: TState) => void;
  /** The backend async transaction request */
  request: () => Promise<ActionResult<TData>>;
  /** Factual success message or callback with server-confirmed data */
  successMessage?:
    | string
    | ((data: TData) => { title: string; description?: string } | string);
  /** Optional callback on successful backend confirmation */
  onSuccess?: (data: TData) => void;
  /** Optional callback on error */
  onError?: (error: string, fields?: Record<string, string>, duplicates?: unknown[]) => void;
};

/**
 * Hook for the Anticipation Method (Optimistic UI with Rollback and Shake Animation).
 *
 * Pattern:
 * 1. Anticipate success immediately so the UI reflects the change with zero lag.
 * 2. Background transaction executes while subtle anticipation animation buys time.
 * 3. On success: commits state and fires factual success alert with server data.
 * 4. On error: bounces back, triggers shake animation on the card/form, rolls back
 *    optimistic state, and syncs factual error alert directly with backend response.
 */
export function useAnticipation<TState = unknown>() {
  const [pending, startTransition] = useTransition();
  const [shaking, setShaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const shakeTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const triggerShake = useCallback(() => {
    if (shakeTimeoutRef.current) clearTimeout(shakeTimeoutRef.current);
    setShaking(true);
    shakeTimeoutRef.current = setTimeout(() => {
      setShaking(false);
    }, 480);
  }, []);

  const reset = useCallback(() => {
    setError(null);
    setFieldErrors({});
    setShaking(false);
  }, []);

  const execute = useCallback(
    async <TData,>(options: AnticipationOptions<TData, TState>) => {
      // 1. Snapshot previous state & apply optimistic anticipation immediately
      const previous = options.anticipate();
      setError(null);
      setFieldErrors({});

      startTransition(async () => {
        try {
          const result = await options.request();

          if (!result.ok) {
            // 2. Failure: Rollback optimistic update immediately & shake container
            options.rollback(previous);
            triggerShake();
            setError(result.error);
            if (result.fields) setFieldErrors(result.fields);

            // Factual error alert synced with exact response
            toast.error(result.error || "Action could not be completed.");
            options.onError?.(result.error, result.fields, result.duplicates);
            return;
          }

          // 3. Success: Factual alert synchronized with backend confirmation
          if (options.successMessage) {
            const msg =
              typeof options.successMessage === "function"
                ? options.successMessage(result.data)
                : options.successMessage;

            if (typeof msg === "string") {
              toast.success(msg);
            } else {
              toast.success(msg.title, { description: msg.description });
            }
          }

          options.onSuccess?.(result.data);
        } catch (err) {
          // Unexpected failure / network drop: Rollback & shake
          options.rollback(previous);
          triggerShake();
          const errText =
            err instanceof Error ? err.message : "Connection failed. Please try again.";
          setError(errText);
          toast.error(errText);
          options.onError?.(errText);
        }
      });
    },
    [triggerShake]
  );

  return {
    pending,
    shaking,
    error,
    fieldErrors,
    shakeClass: shaking
      ? "animate-shake ring-2 ring-danger/40 ring-offset-2 transition-all duration-300"
      : "",
    anticipateClass: pending ? "animate-anticipate pointer-events-none opacity-90" : "",
    execute,
    triggerShake,
    reset,
    setError,
    setFieldErrors,
  };
}
