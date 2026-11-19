"use client";

import { useRouter } from "next/navigation";
import type { ComponentProps, MouseEvent, ReactNode } from "react";
import { Button as ShadButton } from "@/src/components/ui/button";
import { Spinner } from "@/src/components/ui/spinner";
import { SHAD_SIZE, SHAD_VARIANT, type Size, type Variant } from "./button-look";

// Every screen's button: shadcn/ui's, as Studio Admin uses it (2026-11-19), with the props every screen already
// passes (it was Ant Design's; the file keeps its name so nothing else changes).
export type { Size, Variant } from "./button-look";

type ButtonProps = Omit<ComponentProps<"button">, "type" | "color"> & {
  variant?: Variant;
  size?: Size;
  /** Shows a spinner and blocks clicks while the action runs. */
  loading?: boolean;
  icon?: ReactNode;
  type?: "button" | "submit" | "reset";
};

export function Button({ variant = "default", size = "md", loading = false, icon, type = "button", disabled, children, ...rest }: ButtonProps) {
  return (
    <ShadButton
      suppressHydrationWarning
      variant={SHAD_VARIANT[variant]}
      size={SHAD_SIZE[size]}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Spinner data-icon="inline-start" /> : icon}
      {children}
    </ShadButton>
  );
}

type LinkButtonProps = Omit<ComponentProps<"a">, "href" | "type" | "color"> & {
  href: string;
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
  scroll?: boolean;
  /** Next's link option; false skips loading the page ahead. */
  prefetch?: boolean;
};

/** A link drawn as a button. A plain click moves within the app; Ctrl-click and the like still open a new tab, and a `download` link fetches its file. */
export function LinkButton({ href, variant = "default", size = "md", icon, children, onClick, scroll, prefetch, ...rest }: LinkButtonProps) {
  const router = useRouter();
  // Load the page ahead when the pointer comes near, as a Next link does.
  const ahead = () => prefetch !== false && rest.download === undefined && router.prefetch(href);
  function go(e: MouseEvent<HTMLAnchorElement>) {
    onClick?.(e);
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || rest.target === "_blank" || rest.download !== undefined) return;
    e.preventDefault();
    router.push(href, { scroll: scroll ?? true });
  }
  return (
    <ShadButton asChild variant={SHAD_VARIANT[variant]} size={SHAD_SIZE[size]}>
      <a suppressHydrationWarning href={href} onClick={go} onMouseEnter={ahead} {...rest}>
        {icon}
        {children}
      </a>
    </ShadButton>
  );
}
