import type { ReactNode } from "react";

// The pieces of a dialog's body, so every dialog is laid out the same way:
// short fields side by side, and related settings grouped in a panel with a
// line saying what they're for. The frame (title, close, Cancel and the main
// action) is Ant's modal, styled once in app/globals.css.

/** Two short fields side by side (one above the other on a phone). */
export function FieldRow({ children }: { children: ReactNode }) {
  return <div className="grid gap-4 sm:grid-cols-2">{children}</div>;
}

/** Settings that belong together, in a light panel; `hint` says what they're for. */
export function DialogPanel({ title, hint, children }: { title?: string; hint?: string; children: ReactNode }) {
  return (
    <section>
      {title && <p className="mb-1.5 text-sm font-medium text-ink">{title}</p>}
      <div className="space-y-3 rounded-xl border border-rule p-4">
        {children}
        {hint && <p className="text-meta text-ink-3">{hint}</p>}
      </div>
    </section>
  );
}
