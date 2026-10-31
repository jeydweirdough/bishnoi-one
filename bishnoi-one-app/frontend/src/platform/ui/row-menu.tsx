"use client";

import { Modal } from "antd";
import { Ellipsis } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { toast } from "sonner";

// What can be done to one row, behind a ⋯ at its end (decided 2026-10-26): the same three dots as a
// page's More menu, so a person learns one place to look on every table (Jakob's law). Items are
// the row's pages (open, edit, start a quote) and its actions (delete), only those the person's
// role allows; anything that can't be undone asks first. The panel floats over the page, so a
// table's edge never cuts it off.

type Result = { ok: true } | { ok: false; error: string };

export type RowMenuItem =
  | { label: string; icon: ReactNode; href: string; download?: boolean }
  /** Something on the page itself (open a dialog), from a menu drawn on the client. */
  | { label: string; icon: ReactNode; onSelect: () => void }
  | {
      label: string;
      icon: ReactNode;
      /** A server action already bound to the row (deleteCompany.bind(null, id)). */
      run: () => Promise<Result | { ok: true; data?: unknown }>;
      danger?: boolean;
      /** Asked before it runs, for what can't be undone. */
      confirm?: string;
      /** Said when it's done. */
      done?: string;
    }
  | "divider";

const ROW = "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm hover:bg-bench focus-visible:bg-bench focus-visible:outline-none";

/** `always`: the ⋯ shows at all times, not only when its row is hovered (where it's the only way to the row's actions: People). */
export function RowMenu({ label, items, always = false }: { label: string; items: RowMenuItem[]; always?: boolean }) {
  const router = useRouter();
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState<{ top: number; right: number } | null>(null);
  const [busy, start] = useTransition();
  const shown = items.filter((x, i, all) => x !== "divider" || (i > 0 && i < all.length - 1 && all[i - 1] !== "divider"));

  useEffect(() => {
    if (!at) return;
    const away = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!panel.current?.contains(t) && !button.current?.contains(t)) setAt(null);
    };
    const close = () => setAt(null);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setAt(null);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [at]);

  if (!shown.some((x) => x !== "divider")) return null;

  function toggle(e: React.MouseEvent) {
    // A row is often a link: the menu is its own target.
    e.preventDefault();
    e.stopPropagation();
    if (at) return setAt(null);
    const r = button.current?.getBoundingClientRect();
    if (r) setAt({ top: r.bottom + 6, right: window.innerWidth - r.right });
  }

  function act(item: Extract<RowMenuItem, { run: unknown }>) {
    setAt(null);
    const go = () =>
      start(async () => {
        const r = await item.run();
        if (!r.ok) return void toast.error("error" in r ? r.error : "That didn't work.");
        toast.success(item.done ?? "Done");
        router.refresh();
      });
    if (item.confirm) Modal.confirm({ title: item.confirm, okText: item.label, okButtonProps: { danger: item.danger }, cancelText: "Cancel", onOk: go });
    else go();
  }

  return (
    <>
      <button
        ref={button}
        suppressHydrationWarning
        type="button"
        onClick={toggle}
        disabled={busy}
        aria-haspopup="menu"
        aria-expanded={Boolean(at)}
        aria-label={label}
        title="Actions"
        className={`relative z-[1] grid size-8 shrink-0 place-items-center rounded-lg text-ink-3 transition-all hover:bg-bench hover:text-ink focus-visible:ring-2 focus-visible:ring-sage focus-visible:outline-none disabled:opacity-40 ${
          at
            ? "bg-bench text-ink opacity-100"
            : always
              ? "border border-rule bg-sheet opacity-100"
              : "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100"
        }`}
      >
        <Ellipsis className="size-[1.125rem]" aria-hidden />
      </button>
      {at &&
        createPortal(
          <div
            ref={panel}
            role="menu"
            aria-label={label}
            style={{ top: at.top, right: at.right }}
            className="fixed z-[60] w-56 rounded-xl border border-rule bg-white p-1.5 shadow-[0_12px_32px_rgba(20,20,20,0.12)]"
          >
            {shown.map((item, i) => {
              if (item === "divider") return <div key={`d${i}`} role="separator" className="my-1 border-t border-rule" />;
              const body = (
                <>
                  <span className={`inline-flex shrink-0 [&>svg]:size-4 ${"danger" in item && item.danger ? "text-danger" : "text-ink-3"}`} aria-hidden>
                    {item.icon}
                  </span>
                  {item.label}
                </>
              );
              if ("onSelect" in item)
                return (
                  <button key={item.label} suppressHydrationWarning type="button" role="menuitem" onClick={() => (setAt(null), item.onSelect())} className={`${ROW} text-ink`}>
                    {body}
                  </button>
                );
              if ("href" in item)
                return item.download ? (
                  <a key={item.label} role="menuitem" href={item.href} download className={`${ROW} text-ink`} onClick={() => setAt(null)}>
                    {body}
                  </a>
                ) : (
                  <Link key={item.label} role="menuitem" href={item.href} className={`${ROW} text-ink`} onClick={() => setAt(null)}>
                    {body}
                  </Link>
                );
              return (
                <button key={item.label} suppressHydrationWarning type="button" role="menuitem" onClick={() => act(item)} className={`${ROW} ${item.danger ? "text-danger hover:bg-danger-tint" : "text-ink"}`}>
                  {body}
                </button>
              );
            })}
          </div>,
          document.body,
        )}
    </>
  );
}
