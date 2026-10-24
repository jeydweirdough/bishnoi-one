"use client";

import { Modal } from "antd";
import { ArrowRight, Building2, CornerDownLeft, FileText, Handshake, Package, Plus, Search, UserRound, type LucideIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { Fragment, useEffect, useMemo, useRef, useState, useTransition } from "react";
import { searchAll, type SearchFact, type SearchGroup, type SearchKind } from "@/src/modules/crm/actions/search";
import { peso } from "@/src/platform/lib/format";
import { Amount } from "@/src/platform/ui/amount";

// The command menu (benchmark G2, after Twenty's Cmd+K; laid out as the UI
// kit's search palette, 2026-10-22): one box to find any customer, contact,
// deal, quote or product, or to go somewhere or start something. Ctrl+K (⌘K on
// a Mac), or "/" when not typing, opens it. Typing shows scope tabs with how
// many of each match (Tab moves between them), the matches grouped by kind, and
// a preview of the selected one with its next steps. The arrow keys move, Enter
// opens, Esc closes. Records come from the API, kept to what the person may
// see; the actions are the ones their role allows.

const OPEN_EVENT = "bishnoi:command-menu";
/** Shown per kind under All; a scope tab shows up to what the API sends (12). */
const PER_GROUP = 4;

/** The top bar's Search button (drawn on the phone's bar and the desktop's): it asks the one menu to open. */
export function CommandMenuButton() {
  const mac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
  const ask = () => window.dispatchEvent(new Event(OPEN_EVENT));
  return (
    <>
      <button suppressHydrationWarning
        type="button"
        onClick={ask}
        className="hidden h-10 items-center gap-2 rounded-[11px] border border-rule bg-bench pr-2 pl-3 text-meta text-ink-3 transition-colors hover:border-[#c9c9c5] hover:bg-sheet hover:text-ink md:inline-flex"
        aria-keyshortcuts="Control+K"
      >
        <Search className="size-4" aria-hidden />
        <span className="w-40 text-left">Search or jump to…</span>
        <kbd className="rounded-md border border-rule bg-sheet px-1.5 py-0.5 font-sans text-[0.6875rem] text-ink-3">{mac ? "⌘K" : "Ctrl K"}</kbd>
      </button>
      <button suppressHydrationWarning type="button" onClick={ask} aria-label="Search" className="grid size-10 place-items-center rounded-lg text-ink-2 hover:bg-sheet hover:text-ink md:hidden">
        <Search className="size-5" aria-hidden />
      </button>
    </>
  );
}

export type MenuAction = { label: string; href: string; group: "Go to" | "Create"; keywords?: string };

type Scope = "all" | SearchKind;

type Row = {
  key: string;
  group: string;
  title: string;
  sub?: string | null;
  href: string;
  kind: SearchKind | "go" | "create";
  facts?: SearchFact[];
  actions?: { label: string; href: string }[];
  /** Under All, a group with more than it shows: the tab that shows them. */
  more?: { scope: SearchKind; total: number };
};

/** Each kind's icon and colour, on its rows, tabs and preview. */
const KINDS: Record<Row["kind"], { icon: LucideIcon; colour: string; one: string }> = {
  customers: { icon: Building2, colour: "#2f7fd8", one: "Customer" },
  contacts: { icon: UserRound, colour: "#7a5bd6", one: "Contact" },
  deals: { icon: Handshake, colour: "#3f8f4f", one: "Deal" },
  quotes: { icon: FileText, colour: "#c77d14", one: "Quote" },
  products: { icon: Package, colour: "#0f8a8a", one: "Product" },
  go: { icon: ArrowRight, colour: "#5f5f5a", one: "Page" },
  create: { icon: Plus, colour: "#141414", one: "Create" },
};

function typingIn(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

/** The text with what was typed marked. */
function Marked({ text, q }: { text: string; q: string }) {
  const at = q ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (at < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, at)}
      <mark className="rounded-[3px] bg-[#f6e7a8] px-px text-inherit">{text.slice(at, at + q.length)}</mark>
      {text.slice(at + q.length)}
    </>
  );
}

function KindIcon({ kind, big = false }: { kind: Row["kind"]; big?: boolean }) {
  const { icon: Icon, colour } = KINDS[kind];
  return (
    <span
      className={`grid shrink-0 place-items-center ${big ? "size-11 rounded-xl" : "size-[34px] rounded-[9px]"}`}
      style={{ background: `color-mix(in srgb, ${colour} 13%, transparent)`, color: colour }}
    >
      <Icon className={big ? "size-5" : "size-4"} aria-hidden />
    </span>
  );
}

export function CommandMenu({ actions }: { actions: MenuAction[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [scope, setScope] = useState<Scope>("all");
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
      setScope("all");
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

  const text = q.trim();
  // The tabs: All, then each kind that matched, with how many.
  const scopes: { key: Scope; label: string; total: number }[] = useMemo(
    () => (text ? [{ key: "all" as Scope, label: "All", total: found.reduce((n, g) => n + g.total, 0) }, ...found.map((g) => ({ key: g.kind as Scope, label: g.label, total: g.total }))] : []),
    [text, found],
  );
  const inScope = scopes.some((s) => s.key === scope) ? scope : "all";

  const rows: Row[] = useMemo(() => {
    const lower = text.toLowerCase();
    const records: Row[] = found
      .filter((g) => inScope === "all" || g.kind === inScope)
      .flatMap((g) => {
        const shown = inScope === "all" ? g.items.slice(0, PER_GROUP) : g.items;
        return shown.map((i, n) => ({
          key: `${g.kind}:${i.id}`,
          group: g.label,
          title: i.title,
          sub: i.sub,
          href: i.href,
          kind: g.kind,
          facts: i.facts,
          actions: i.actions,
          more: inScope === "all" && n === 0 && g.total > shown.length ? { scope: g.kind, total: g.total } : undefined,
        }));
      });
    if (inScope !== "all") return records;
    const matched = actions.filter((a) => !lower || `${a.label} ${a.keywords ?? ""}`.toLowerCase().includes(lower));
    const acts: Row[] = matched.slice(0, lower ? 6 : 12).map((a) => ({
      key: `act:${a.href}:${a.label}`,
      group: a.group,
      title: a.label,
      href: a.href,
      kind: a.group === "Create" ? "create" : "go",
    }));
    // Typing a name: records first. Nothing typed: where to go and what to start.
    return lower ? [...records, ...acts] : acts;
  }, [text, found, actions, inScope]);

  useEffect(() => setActive(0), [q, found, inScope]);
  useEffect(() => {
    listRef.current?.querySelector(`[data-row="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const close = () => {
    setOpen(false);
    setQ("");
    setScope("all");
  };
  const go = (href: string | undefined) => {
    if (!href) return;
    close();
    router.push(href);
  };
  const nextScope = (back: boolean) => {
    if (scopes.length < 2) return;
    const i = scopes.findIndex((s) => s.key === inScope);
    setScope(scopes[(i + (back ? scopes.length - 1 : 1)) % scopes.length].key);
  };

  const current = rows[active];
  const shownGroup = inScope === "all" ? null : found.find((g) => g.kind === inScope);
  let lastGroup = "";
  return (
    <Modal
      open={open}
      onCancel={close}
      footer={null}
      closable={false}
      width={820}
      style={{ top: "9vh" }}
      styles={{ body: { padding: 0 }, container: { padding: 0, overflow: "hidden", borderRadius: 18 } }}
      destroyOnHidden
    >
      <div className="flex items-center gap-3 border-b border-rule px-[18px] py-3.5">
        <Search className="size-5 shrink-0 text-ink" aria-hidden />
        <input suppressHydrationWarning
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
              go(current?.href);
            } else if (e.key === "Tab" && scopes.length > 1) {
              e.preventDefault();
              nextScope(e.shiftKey);
            }
          }}
          placeholder="Search customers, contacts, deals, quotes, products, or type a page"
          aria-label="Search"
          role="combobox"
          aria-expanded="true"
          aria-controls="command-results"
          aria-activedescendant={current ? `command-row-${active}` : undefined}
          className="h-7 min-w-0 flex-1 bg-transparent text-[1.0625rem] text-ink outline-none placeholder:text-ink-3"
        />
        {searching && <span className="text-meta text-ink-3">Searching…</span>}
      </div>
      {scopes.length > 1 && (
        <div role="tablist" aria-label="Search in" className="flex gap-1.5 overflow-x-auto border-b border-rule px-3.5 py-2.5 [scrollbar-width:none]">
          {scopes.map((s) => {
            const on = s.key === inScope;
            const Icon = s.key === "all" ? null : KINDS[s.key].icon;
            return (
              <button suppressHydrationWarning
                key={s.key}
                type="button"
                role="tab"
                aria-selected={on}
                onClick={() => setScope(s.key)}
                className={`inline-flex h-8 shrink-0 items-center gap-1.5 rounded-[9px] border px-3 text-[0.78125rem] font-medium whitespace-nowrap transition-colors ${
                  on ? "border-ink bg-ink text-white" : "border-rule bg-sheet text-ink-2 hover:border-[#c9c9c5] hover:text-ink"
                }`}
              >
                {Icon && <Icon className="size-3.5" aria-hidden />}
                {s.label}
                <span className={`text-[0.6875rem] ${on ? "text-white/80" : "text-ink-3"}`}>{s.total}</span>
              </button>
            );
          })}
        </div>
      )}
      <div className="grid min-h-0 md:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <div ref={listRef} id="command-results" role="listbox" className="max-h-[min(26rem,60vh)] overflow-y-auto px-2 pt-1.5 pb-2.5">
          {rows.length === 0 ? (
            <p className="px-4 py-8 text-center text-meta text-ink-3">{text ? (searching ? "Searching…" : `Nothing matches “${text}”. Try another word, or a customer code or quote number.`) : "Start typing."}</p>
          ) : (
            rows.map((row, i) => {
              const heading = row.group !== lastGroup ? row.group : null;
              lastGroup = row.group;
              return (
                <Fragment key={row.key}>
                  {heading && (
                    <div className="flex items-center justify-between px-2.5 pt-3 pb-1.5">
                      <span className="text-[0.6875rem] font-semibold tracking-[0.06em] text-ink-3 uppercase">{heading}</span>
                      {row.more && (
                        <button suppressHydrationWarning type="button" onClick={() => setScope(row.more!.scope)} className="text-[0.71875rem] font-medium text-ink-2 hover:text-ink hover:underline">
                          See all {row.more.total}
                        </button>
                      )}
                    </div>
                  )}
                  <div
                    id={`command-row-${i}`}
                    data-row={i}
                    role="option"
                    aria-selected={i === active}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => go(row.href)}
                    className={`flex cursor-pointer items-center gap-3 rounded-[10px] px-2.5 py-2 ${i === active ? "bg-mint" : ""}`}
                  >
                    <KindIcon kind={row.kind} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[0.84375rem] font-medium text-ink">
                        <Marked text={row.title} q={text} />
                      </span>
                      {row.sub && (
                        <span className="block truncate text-meta text-ink-3">
                          <Marked text={row.sub} q={text} />
                        </span>
                      )}
                    </span>
                    <CornerDownLeft className={`size-4 shrink-0 ${i === active ? "text-ink-3" : "text-transparent"}`} aria-hidden />
                  </div>
                </Fragment>
              );
            })
          )}
          {shownGroup && shownGroup.total > shownGroup.items.length && (
            <p className="px-2.5 pt-2 text-meta text-ink-3">
              Showing {shownGroup.items.length} of {shownGroup.total}. Type more to narrow it.
            </p>
          )}
        </div>
        <Preview row={current} onGo={go} />
      </div>
      <div className="flex flex-wrap gap-4 border-t border-rule px-[18px] py-2.5 text-[0.71875rem] text-ink-3">
        <span>
          <Key>↑</Key> <Key>↓</Key> move
        </span>
        <span>
          <Key>↵</Key> open
        </span>
        {scopes.length > 1 && (
          <span>
            <Key>Tab</Key> next tab
          </span>
        )}
        <span className="flex-1" />
        <span>
          <Key>Esc</Key> close
        </span>
      </div>
    </Modal>
  );
}

function Key({ children }: { children: React.ReactNode }) {
  return <kbd className="rounded-md border border-rule bg-sheet px-1.5 py-0.5 font-sans text-[0.6875rem] text-ink-3">{children}</kbd>;
}

/** The selected row: what it is, a few facts, and its next steps (the first is what Enter does). */
function Preview({ row, onGo }: { row: Row | undefined; onGo: (href: string) => void }) {
  const steps = row ? (row.actions?.length ? row.actions : [{ label: row.kind === "create" ? row.title : `Open ${row.title.toLowerCase()}`, href: row.href }]) : [];
  return (
    <div className="hidden content-start gap-3.5 overflow-y-auto border-l border-rule bg-bench p-[18px] md:grid md:max-h-[min(26rem,60vh)]">
      {!row ? (
        <p className="text-meta text-ink-3">Nothing selected.</p>
      ) : (
        <>
          <div className="flex items-center gap-3">
            <KindIcon kind={row.kind} big />
            <div className="min-w-0">
              <p className="truncate text-[0.9375rem] font-semibold text-ink">{row.title}</p>
              <p className="text-meta text-ink-3">{KINDS[row.kind].one}</p>
            </div>
          </div>
          {row.facts && row.facts.length > 0 && (
            <dl className="overflow-hidden rounded-xl border border-rule bg-sheet">
              {row.facts.map((f) => (
                <div key={f.label} className="flex justify-between gap-2.5 border-t border-rule px-3 py-2 text-[0.78125rem] first:border-t-0">
                  <dt className="text-ink-3">{f.label}</dt>
                  <dd className="min-w-0 truncate text-right font-medium text-ink">{f.amount !== undefined ? <Amount text={peso(f.amount)} /> : f.value}</dd>
                </div>
              ))}
            </dl>
          )}
          <div className="grid gap-1.5">
            {steps.map((s, i) => (
              <button suppressHydrationWarning
                key={s.href + s.label}
                type="button"
                onClick={() => onGo(s.href)}
                className="flex h-[38px] items-center gap-2.5 rounded-[10px] border border-rule bg-sheet px-3 text-left text-[0.8125rem] font-medium text-ink transition-colors hover:border-ink"
              >
                {/^New /.test(s.label) ? <Plus className="size-4 text-ink-3" aria-hidden /> : <ArrowRight className="size-4 text-ink-3" aria-hidden />}
                <span className="min-w-0 flex-1 truncate">{s.label}</span>
                {i === 0 && <Key>↵</Key>}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
