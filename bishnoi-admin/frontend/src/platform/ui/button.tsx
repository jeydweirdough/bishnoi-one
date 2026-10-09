import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

type Variant = "primary" | "default" | "quiet" | "danger";
type Size = "md" | "sm";

const base =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-55";

const variants: Record<Variant, string> = {
  primary: "bg-hema text-white hover:bg-hema-hover",
  default: "bg-sheet text-ink border border-ink hover:bg-mint",
  quiet: "text-ink hover:bg-mint",
  danger: "bg-danger text-white hover:brightness-95",
};

const sizes: Record<Size, string> = {
  md: "h-10 px-5 text-sm",
  sm: "h-8 px-3.5 text-meta",
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
    <button
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
