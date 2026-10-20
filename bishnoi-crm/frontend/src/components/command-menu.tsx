"use client";

import { Modal } from "antd";
import { ArrowRight, CornerDownLeft, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { searchAll, type SearchGroup } from "@/src/actions/search";

// The command menu (benchmark G2, after Twenty's Cmd+K): one box to find any
// customer, contact, deal, quote or product, or to go somewhere or start
// something. Ctrl+K (⌘K on a Mac), or "/" when not typing, opens it; the arrow
// keys move, Enter opens, Esc closes. Records come from the API, kept to what
// the person may see; the actions are the ones their role allows.

const OPEN_EVENT = "bishnoi:command-menu";

/** The top bar's Search button (drawn on the phone's bar and the desktop's): it asks the one menu to open. */
export function CommandMenuButton() {
  const mac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
  const ask = () => window.dispatchEvent(new Event(OPEN_EVENT));
  return (
    <>
      <button
        type="button"
        onClick={ask}
        className="hidden h-10 items-center gap-2 rounded-lg border border-rule bg-sheet pr-2 pl-3 text-meta text-ink-3 transition-colors hover:border-ink-3 hover:text-ink md:inline-flex"
        aria-keyshortcuts="Control+K"
      >
        <Search className="size-4" aria-hidden />
        <span className="w-40 text-left">Search or jump to…</span>
        <kbd className="rounded border border-rule bg-bench px-1.5 font-sans text-[0.6875rem] text-ink-3">{mac ? "⌘K" : "Ctrl K"}</kbd>
      </button>
      <button type="button" onClick={ask} aria-label="Search" className="grid size-10 place-items-center rounded-lg text-ink-2 hover:bg-sheet hover:text-ink md:hidden">
        <Search className="size-5" aria-hidden />
      </button>
    </>
  );
}

export type MenuAction = { label: string; href: string; group: "Go to" | "Create"; keywords?: string };

type Row = { key: string; group: string; title: string; sub?: string | null; href: string };

function typingIn(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

export function CommandMenu({ actions }: { actions: MenuAction[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [found, setFound] = useState<SearchGroup[]>([]);
  const [active, setActive] = useState(0);
  const [searching, start] = useTransition();
  const listRef = useRef<HTMLDivElement>(null);

  // Ctrl+K / ⌘K anywhere; "/" when not typing in a field.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.key === "k" || e.key === "K") && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "/" && !open && !typingIn(e.target)) {
        e.preventDefault();
        setOpen(true);
      }
    };
    const onAsk = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_EVENT, onAsk);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(OPEN_EVENT, onAsk);
    };
  }, [open]);

  // Records as the person types, a moment after they stop.
  useEffect(() => {
    const text = q.trim();
    if (!text) {
      setFound([]);
      return;
    }
    const t = setTimeout(() => {
      start(async () => {
        const r = await searchAll(text);
        setFound(r.ok ? r.data : []);
      });
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  const rows: Row[] = useMemo(() => {
    const text = q.trim().toLowerCase();
    const matched = actions.filter((a) => !text || `${a.label} ${a.keywords ?? ""}`.toLowerCase().includes(text));
    const records = found.flatMap((g) => g.items.map((i) => ({ key: `${g.kind}:${i.id}`, group: g.label, title: i.title, sub: i.sub, href: i.href })));
    const acts = matched.slice(0, text ? 6 : 12).map((a) => ({ key: `act:${a.href}:${a.label}`, group: a.group, title: a.label, href: a.href }));
    // Typing a name: records first. Nothing typed: where to go and what to start.
    return text ? [...records, ...acts] : acts;
  }, [q, found, actions]);

  useEffect(() => setActive(0), [q, found]);
  useEffect(() => {
    listRef.current?.querySelector(`[data-row="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const close = () => {
    setOpen(false);
    setQ("");
  };
  const go = (row: Row | undefined) => {
    if (!row) return;
    close();
    router.push(row.href);
  };

  let lastGroup = "";
  return (
    <>
      <Modal open={open} onCancel={close} footer={null} closable={false} width={620} styles={{ body: { padding: 0 } }} destroyOnHidden>
        <div className="flex items-center gap-2 border-b border-rule px-4">
          <Search className="size-4 shrink-0 text-ink-3" aria-hidden />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(rows.length - 1, a + 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(0, a - 1));
              } else if (e.key === "Enter") {
                e.preventDefault();
                go(rows[active]);
              }
            }}
            placeholder="Search customers, contacts, deals, quotes, products, or type a page"
            aria-label="Search"
            role="combobox"
            aria-expanded="true"
            aria-controls="command-results"
            aria-activedescendant={rows[active] ? `command-row-${active}` : undefined}
            className="h-12 min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-3"
          />
          {searching && <span className="text-meta text-ink-3">Searching…</span>}
        </div>
        <div ref={listRef} id="command-results" role="listbox" className="max-h-[22rem] overflow-y-auto py-2">
          {rows.length === 0 ? (
            <p className="px-4 py-6 text-center text-meta text-ink-3">{q.trim() ? (searching ? "Searching…" : `Nothing matches “${q.trim()}”.`) : "Start typing."}</p>
          ) : (
            rows.map((row, i) => {
              const heading = row.group !== lastGroup ? row.group : null;
              lastGroup = row.group;
              return (
                <div key={row.key}>
                  {heading && <p className="px-4 pt-2 pb-1 text-[0.6875rem] font-semibold tracking-wide text-ink-3 uppercase">{heading}</p>}
                  <div
                    id={`command-row-${i}`}
                    data-row={i}
                    role="option"
                    aria-selected={i === active}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => go(row)}
                    className={`mx-2 flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 ${i === active ? "bg-mint" : ""}`}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-ink">{row.title}</span>
                      {row.sub && <span className="block truncate text-meta text-ink-3">{row.sub}</span>}
                    </span>
                    {i === active ? <CornerDownLeft className="size-4 shrink-0 text-ink-3" aria-hidden /> : <ArrowRight className="size-4 shrink-0 text-transparent" aria-hidden />}
                  </div>
                </div>
              );
            })
          )}
        </div>
        <p className="border-t border-rule px-4 py-2 text-[0.6875rem] text-ink-3">↑ ↓ to move · Enter to open · Esc to close</p>
      </Modal>
    </>
  );
}
