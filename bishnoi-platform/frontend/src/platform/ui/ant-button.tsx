"use client";

import { Button as AntButton } from "antd";
import { useRouter } from "next/navigation";
import type { ComponentProps, MouseEvent, ReactNode } from "react";

// Ant Design's button, with the props every screen already passes.
export type Variant = "primary" | "default" | "quiet" | "danger";
export type Size = "md" | "sm";

function look(variant: Variant): Pick<ComponentProps<typeof AntButton>, "type" | "danger" | "color" | "variant"> {
  if (variant === "primary") return { type: "primary" };
  if (variant === "danger") return { type: "primary", danger: true };
  if (variant === "quiet") return { type: "text" };
  return { type: "default" };
}

type ButtonProps = Omit<ComponentProps<"button">, "type" | "color"> & {
  variant?: Variant;
  size?: Size;
  /** Shows a spinner and blocks clicks while the action runs. */
  loading?: boolean;
  icon?: ReactNode;
  type?: "button" | "submit" | "reset";
};

export function Button({ variant = "default", size = "md", loading = false, icon, type = "button", children, ...rest }: ButtonProps) {
  return (
    <AntButton suppressHydrationWarning {...look(variant)} size={size === "sm" ? "small" : "middle"} htmlType={type} loading={loading} icon={icon} {...rest}>
      {children}
    </AntButton>
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

/** A link drawn as an Ant button. A plain click moves within the app; Ctrl-click and the like still open a new tab, and a `download` link fetches its file. */
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
    <AntButton suppressHydrationWarning
      {...look(variant)}
      size={size === "sm" ? "small" : "middle"}
      href={href}
      icon={icon}
      onClick={go as unknown as ComponentProps<typeof AntButton>["onClick"]}
      onMouseEnter={ahead}
      {...(rest as Record<string, unknown>)}
    >
      {children}
    </AntButton>
  );
}
