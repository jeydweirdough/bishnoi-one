// Buttons are Ant Design's (ant-button.tsx). What's left here is for a plain
// <a> or <label> that has to look like one: an Ant button's shape, in classes
// a server-rendered page can use.
export { Button, LinkButton } from "./ant-button";
import type { Size, Variant } from "./ant-button";

const base =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-55";

const variants: Record<Variant, string> = {
  primary: "bg-hema text-white hover:bg-hema-hover",
  default: "bg-sheet text-ink border border-ink hover:bg-mint",
  quiet: "text-ink-2 hover:bg-[#f4f4f2] hover:text-ink",
  danger: "bg-danger text-white hover:bg-[#941c13]",
};

const sizes: Record<Size, string> = {
  md: "h-9 px-[18px] text-sm",
  sm: "h-7 px-3 text-sm",
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
