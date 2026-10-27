"use client";

import { Modal } from "antd";
import { Eye, EyeOff, Search } from "lucide-react";
import { useEffect, useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { startViewAs, stopViewAs } from "./view-as-actions";

// View as (decided 2026-10-26): an administrator sees the module exactly as one of its people does,
// from the role that may do most down to the one that may do least: their menus, home, records and
// actions. Read-only, and said so across the top until they stop.

export type ViewAsRole = { role: string; size: number; people: { id: string; fullName: string; email: string }[] };

/** Leaves the page the way a fresh visit would, so every part is drawn as the new person sees it. */
const reload = (home: string) => window.location.assign(home);

/** Opens the View as dialog: sent by the account menu's "View as" (account-menu.tsx). */
export const VIEW_AS_EVENT = "bishnoi:view-as";

/** Whom to view the module as, by role: opened from the account menu. */
export function ViewAsButton({ roles }: { roles: ViewAsRole[] }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const show = () => setOpen(true);
    window.addEventListener(VIEW_AS_EVENT, show);
    return () => window.removeEventListener(VIEW_AS_EVENT, show);
  }, []);
  const [q, setQ] = useState("");
  const [busy, start] = useTransition();
  const shown = useMemo(() => {
    const t = q.trim().toLowerCase();
    return roles
      .map((g) => ({ ...g, people: t ? g.people.filter((p) => `${p.fullName} ${p.email} ${g.role}`.toLowerCase().includes(t)) : g.people }))
      .filter((g) => g.people.length);
  }, [q, roles]);

  function pick(id: string) {
    start(async () => {
      const r = await startViewAs(id);
      if (!r.ok) return void toast.error(r.error);
      reload(r.data.home);
    });
  }

  return (
    <>
      <Modal open={open} title="View as" onCancel={() => setOpen(false)} footer={null} width={520} destroyOnHidden>
        <p className="text-sm text-ink-2">See this module exactly as they do: their menus, home, records and actions. Nothing can be changed while viewing.</p>
        <label className="relative mt-3 block">
          <span className="sr-only">Find a person</span>
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
          <input
            suppressHydrationWarning
            autoFocus
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Find a person or role"
            className="h-10 w-full rounded-lg border border-rule bg-bench pr-3 pl-9 text-sm outline-none focus:border-ink focus:bg-white"
          />
        </label>
        <div className="mt-3 max-h-[55dvh] space-y-4 overflow-y-auto pr-1">
          {shown.length === 0 && <p className="py-6 text-center text-sm text-ink-3">Nobody matches.</p>}
          {shown.map((g) => (
            <section key={g.role}>
              <p className="mb-1 flex items-center justify-between text-caps text-ink-3 uppercase">
                {g.role}
                <span className="normal-case">{g.people.length}</span>
              </p>
              <ul className="divide-y divide-rule rounded-xl border border-rule">
                {g.people.map((p) => (
                  <li key={p.id}>
                    <button
                      suppressHydrationWarning
                      type="button"
                      disabled={busy}
                      onClick={() => pick(p.id)}
                      className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-mint/60 disabled:opacity-50"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-ink">{p.fullName}</span>
                        <span className="block truncate text-meta text-ink-3">{p.email}</span>
                      </span>
                      <Eye className="size-4 shrink-0 text-ink-3" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </Modal>
    </>
  );
}

/** Across the top while viewing: whom, read-only, and the way back. */
export function ViewingBar({ name, role }: { name: string; role: string }) {
  const [busy, start] = useTransition();
  return (
    <div role="status" className="fixed top-0 left-1/2 z-[80] flex -translate-x-1/2 items-center gap-3 rounded-b-xl bg-ink py-1.5 pr-1.5 pl-4 text-sm text-white shadow-lg">
      <Eye className="size-4 text-sage" aria-hidden />
      <span>
        Viewing as <b>{name}</b>
        <span className="text-white/70"> · {role} · read-only</span>
      </span>
      <button
        suppressHydrationWarning
        type="button"
        disabled={busy}
        onClick={() =>
          start(async () => {
            const r = await stopViewAs();
            if (!r.ok) return void toast.error(r.error);
            reload(r.data.home);
          })
        }
        className="inline-flex items-center gap-1.5 rounded-lg bg-white/15 px-3 py-1 font-medium hover:bg-white/25 disabled:opacity-50"
      >
        <EyeOff className="size-4" aria-hidden />
        Stop viewing
      </button>
    </div>
  );
}
