// Buttons are Ant Design's (ant-button.tsx). What's left here is for a plain
// <a> or <label> that has to look like one: an Ant button's shape, in classes
// a server-rendered page can use.
export { Button, LinkButton } from "./ant-button";
import type { Size, Variant } from "./ant-button";

const base =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[6px] font-normal transition-colors disabled:cursor-not-allowed disabled:opacity-55";

const variants: Record<Variant, string> = {
  primary: "bg-hema text-white shadow-[0_2px_0_rgb(5_145_255_/_0.1)] hover:bg-hema-hover",
  default: "bg-sheet text-ink border border-rule-strong shadow-[0_2px_0_rgb(0_0_0_/_0.02)] hover:border-hema-hover hover:text-ink",
  quiet: "text-ink hover:bg-hema-tint",
  danger: "bg-[#ff4d4f] text-white hover:bg-[#ff7875]",
};

const sizes: Record<Size, string> = {
  md: "h-8 px-[15px] text-sm",
  sm: "h-6 px-[7px] text-sm",
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
