// Buttons are Ant Design's (ant-button.tsx). What's left here is for a plain
// <a> or <label> that has to look like one: an Ant button's shape, in classes
// a server-rendered page can use.
export { Button, LinkButton } from "./ant-button";
import Link from "next/link";
import type * as React from "react";
import type { Size, Variant } from "./ant-button";

const base =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[9px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-55";

const variants: Record<Variant, string> = {
  primary: "bg-hema text-white hover:bg-hema-hover",
  default: "border border-[#dededa] bg-sheet text-ink shadow-[0_1px_2px_rgba(20,20,20,0.05)] hover:border-[#c9c9c5] hover:bg-[#f4f4f2]",
  quiet: "text-ink-2 hover:bg-[#f4f4f2] hover:text-ink",
  danger: "border border-danger/45 bg-sheet text-danger hover:bg-danger-tint",
};

// The UI kit's sizes (decided 2026-10-22): 40 px, small 34, large 48.
const sizes: Record<Size, string> = {
  md: "h-10 px-[18px] text-sm",
  sm: "h-[34px] gap-1.5 px-3.5 text-[13px]",
  lg: "h-12 gap-2.5 px-6 text-[15px]",
};

export function buttonClass(variant: Variant = "default", size: Size = "md", extra = "") {
  return `${base} ${variants[variant]} ${sizes[size]} ${extra}`;
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
  default: "text-ink-3 hover:bg-bench hover:text-ink",
  /** On a mint or grey surface. */
  soft: "text-ink-2 hover:bg-sheet hover:text-ink",
  danger: "text-ink-3 hover:bg-danger-tint hover:text-danger",
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
      className={`grid shrink-0 place-items-center rounded-lg transition-colors disabled:cursor-not-allowed disabled:opacity-30 ${size === "sm" ? "size-7" : "size-8"} ${pressed ? "bg-hema-tint text-ink" : ICON_TONES[tone]} ${className}`}
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

const QUICK = "inline-flex h-9 items-center gap-2 rounded-lg border border-rule-strong bg-sheet px-3.5 text-sm text-ink-2 transition-colors hover:border-ink hover:bg-mint hover:text-ink";

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
