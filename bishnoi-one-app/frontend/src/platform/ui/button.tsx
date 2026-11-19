// Buttons are shadcn/ui's (ant-button.tsx keeps the props). What's left here is for a plain
// <a> or <label> that has to look like one, in classes a server-rendered page can use.
export { Button, LinkButton } from "./ant-button";
import Link from "next/link";
import type * as React from "react";
import { buttonVariants } from "@/src/components/ui/button";
import { SHAD_SIZE, SHAD_VARIANT, type Size, type Variant } from "./button-look";

// shadcn/ui's button classes (Studio Admin, 2026-11-19), for an <a> or <label> that has to look like a button.
export function buttonClass(variant: Variant = "default", size: Size = "md", extra = "") {
  return buttonVariants({ variant: SHAD_VARIANT[variant], size: SHAD_SIZE[size], className: extra });
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={`inline-block size-3.5 animate-spin rounded-full border-2 border-current border-r-transparent ${className}`}
    />
  );
}

const ICON_TONES = {
  default: "text-muted-foreground hover:bg-muted hover:text-foreground",
  /** On a mint or grey surface. */
  soft: "text-muted-foreground hover:bg-background hover:text-foreground",
  danger: "text-muted-foreground hover:bg-destructive/10 hover:text-destructive",
  /** On a picture or a dark surface. */
  solid: "bg-ink text-white hover:bg-hema-hover",
} as const;

/** A button that is only an icon (⋯, ✕, ↑ ↓, ‹ ›): round, and named for screen readers by `label`. */
export function IconButton({
  label,
  tone = "default",
  size = "md",
  className = "",
  pressed,
  children,
  ...rest
}: Omit<React.ComponentProps<"button">, "aria-label"> & { label: string; tone?: keyof typeof ICON_TONES; size?: "sm" | "md"; pressed?: boolean }) {
  return (
    <button suppressHydrationWarning
      type="button"
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      className={`grid shrink-0 place-items-center rounded-lg transition-colors disabled:cursor-not-allowed disabled:opacity-30 ${size === "sm" ? "size-7" : "size-8"} ${pressed ? "bg-muted text-foreground" : ICON_TONES[tone]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

/** An action written as words in a sentence or a row ("Change", "Show all"): underlined on hover. */
export function TextButton({ tone = "ink", size = "meta", className = "", children, ...rest }: React.ComponentProps<"button"> & { tone?: "ink" | "muted" | "danger"; size?: "meta" | "inherit" }) {
  const colour = tone === "muted" ? "text-ink-3 hover:text-ink" : tone === "danger" ? "text-ink-3 hover:text-danger" : "font-medium text-ink";
  return (
    <button suppressHydrationWarning type="button" className={`inline-flex items-center gap-1 hover:underline disabled:opacity-40 ${size === "meta" ? "text-meta" : ""} ${colour} ${className}`} {...rest}>
      {children}
    </button>
  );
}

const QUICK = buttonVariants({ variant: "outline", size: "lg" });

/** A quick action on a record (Call, Email, Note…): a small pill with its icon. A link with `href`, else a button. */
export function QuickAction({ href, icon, children, ...rest }: React.ComponentProps<"button"> & { href?: string; icon?: React.ReactNode }) {
  const inner = (
    <>
      {icon && (
        <span className="text-ink-3" aria-hidden>
          {icon}
        </span>
      )}
      {children}
    </>
  );
  return href ? (
    <Link href={href} className={QUICK}>
      {inner}
    </Link>
  ) : (
    <button suppressHydrationWarning type="button" className={QUICK} {...rest}>
      {inner}
    </button>
  );
}
