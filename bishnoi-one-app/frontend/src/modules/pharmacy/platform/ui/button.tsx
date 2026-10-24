import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

type Variant = "primary" | "default" | "quiet" | "danger";
type Size = "md" | "sm" | "lg";

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

type ButtonProps = ComponentProps<"button"> & {
  variant?: Variant;
  size?: Size;
  /** Shows a spinner and blocks clicks while the action runs. */
  loading?: boolean;
  icon?: ReactNode;
};

export function Button({
  variant = "default",
  size = "md",
  loading = false,
  icon,
  disabled,
  className = "",
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button suppressHydrationWarning
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={buttonClass(variant, size, className)}
      {...rest}
    >
      {loading ? <Spinner /> : icon}
      {children}
    </button>
  );
}

type LinkButtonProps = ComponentProps<typeof Link> & { variant?: Variant; size?: Size; icon?: ReactNode };

export function LinkButton({ variant = "default", size = "md", icon, className = "", children, ...rest }: LinkButtonProps) {
  return (
    <Link className={buttonClass(variant, size, className)} {...rest}>
      {icon}
      {children}
    </Link>
  );
}
