"use client";

import { MoreHorizontal, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Dropdown, Modal } from "antd";
import { useState, useTransition, type DragEvent, type ReactNode } from "react";
import { toast } from "sonner";

// A board: a column for each stage, a card for each record, in the order work
// moves. The cards read as the CRM's deal cards do: the name, who it's with,
// the amount and its date, one quiet line under. Dragging a card to another
// column takes that step, the same as its button on the record's page; a step
// that needs more than a click opens the record where its form is. A card goes
// only where a move allows, so nothing is offered that would be refused.
//
// The same file is in every app's shared kit (src/platform/ui/board.tsx).

export type BoardColumn = {
  key: string;
  label: string;
  /** A small coloured dot before the name. */
  dot?: string;
  /** Right of the name: "40%". */
  aside?: string;
  /** Under the name: "3 deals · ₱1.2M". */
  note?: string;
  /** In an empty column. */
  hint?: string;
};

export type BoardCard = {
  id: string;
  column: string;
  href: string;
  title: string;
  /** Beside the title: a priority flag, a kind. */
  flag?: ReactNode;
  /** Who or where: the customer, the supplier, from → to. */
  sub?: string;
  /** Bold, bottom left: the amount. */
  value?: string;
  /** Bottom right: its date. */
  when?: string;
  /** The date has passed: it reads red, and the card's top edge too. */
  late?: boolean;
  /** One quiet line under. */
  meta?: string;
  /** False: this person can't move it (another's record). */
  movable?: boolean;
};

/**
 * From a column to another: run `step` here, or open the record (`open`, with
 * {id}) where the step's form is. `from` or `to` "*" is any column; a step of
 * "{to}" is the column moved to (a deal's stage).
 */
export type BoardMove = { from: string; to: string; step?: string; open?: string; label: string; confirm?: string };

type Outcome = { ok: true; data?: unknown } | { ok: false; error: string };

export function Board({ columns, cards, moves, run, newHref, more }: {
  columns: BoardColumn[];
  cards: BoardCard[];
  /** Only the moves this person may make. */
  moves: BoardMove[];
  /** Takes a step: a server action, (record, step). */
  run: (id: string, step: string) => Promise<Outcome>;
  /** The first column's +. */
  newHref?: string;
  /** Under a column: the rest of it ("All received"). */
  more?: Record<string, { href: string; label: string }>;
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [dragging, setDragging] = useState<BoardCard | null>(null);
  const [over, setOver] = useState<string | null>(null);
  // Moved before the page has caught up: shown in its new column at once.
  const [moved, setMoved] = useState<Record<string, string>>({});
  const [asking, setAsking] = useState<{ card: BoardCard; move: BoardMove } | null>(null);

  const columnOf = (c: BoardCard) => moved[c.id] ?? c.column;
  const label = (key: string) => columns.find((c) => c.key === key)?.label ?? key;
  const movesOf = (c: BoardCard): BoardMove[] =>
    c.movable === false
      ? []
      : columns
          .filter((col) => col.key !== columnOf(c))
          .flatMap((col) => {
            const m = moves.find((x) => (x.from === "*" || x.from === columnOf(c)) && (x.to === "*" || x.to === col.key));
            return m ? [{ ...m, to: col.key }] : [];
          });
  const moveTo = (c: BoardCard, to: string) => movesOf(c).find((m) => m.to === to);

  function take(card: BoardCard, move: BoardMove, asked = false) {
    if (move.open) {
      router.push(move.open.replace("{id}", card.id));
      return;
    }
    if (move.confirm && !asked) {
      setAsking({ card, move });
      return;
    }
    setAsking(null);
    const from = columnOf(card);
    setMoved((m) => ({ ...m, [card.id]: move.to }));
    start(async () => {
      const result = await run(card.id, (move.step ?? "").replace("{to}", move.to));
      if (!result.ok) {
        setMoved((m) => ({ ...m, [card.id]: from }));
        toast.error(result.error);
        return;
      }
      toast.success(`${card.title}: ${move.label.replace("{to}", label(move.to)).toLowerCase()}`);
      router.refresh();
    });
  }

  function drop(e: DragEvent, to: string) {
    e.preventDefault();
    setOver(null);
    const card = dragging;
    setDragging(null);
    if (!card || columnOf(card) === to) return;
    const move = moveTo(card, to);
    if (!move) {
      const next = movesOf(card).map((m) => label(m.to));
      toast.message(next.length ? `${card.title} goes to ${next.join(" or ")} next.` : `${card.title} can't be moved from here.`);
      return;
    }
    take(card, move);
  }

  return (
    <>
      <div className="-mx-1 overflow-x-auto px-1 pb-2">
        <div className="grid auto-cols-[minmax(13rem,1fr)] grid-flow-col gap-3">
          {columns.map((col) => {
            const list = cards.filter((c) => columnOf(c) === col.key);
            const target = dragging && columnOf(dragging) !== col.key ? moveTo(dragging, col.key) : undefined;
            return (
              <section
                key={col.key}
                aria-label={col.label}
                onDragOver={(e) => {
                  if (!dragging) return;
                  e.preventDefault();
                  setOver(col.key);
                }}
                onDragLeave={() => setOver((o) => (o === col.key ? null : o))}
                onDrop={(e) => drop(e, col.key)}
                className={`flex min-h-[24rem] min-w-0 flex-col rounded-[20px] border p-2 transition-colors ${
                  over === col.key && target ? "border-sage bg-hema-tint" : target ? "border-dashed border-sage bg-[#f4f4f1]" : "border-transparent bg-[#f4f4f1]"
                }`}
              >
                <header className="mb-2 px-1.5 pt-1">
                  <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
                    {col.dot && <span className="size-2 shrink-0 rounded-full" style={{ background: col.dot }} aria-hidden />}
                    <span className="min-w-0 truncate">{col.label}</span>
                    <span className="font-normal text-ink-3 tabular-nums">{list.length}</span>
                    <span className="ml-auto flex items-center gap-1 text-meta font-normal text-ink-3">
                      {col.aside}
                      {newHref && col.key === columns[0].key && (
                        <Link href={newHref} className="grid size-6 place-items-center rounded-full hover:bg-sheet hover:text-ink" title="New" aria-label="New">
                          <Plus className="size-4" aria-hidden />
                        </Link>
                      )}
                    </span>
                  </h2>
                  {col.note && <p className="text-meta text-ink-3">{col.note}</p>}
                </header>
                {target && <p className="mb-2 rounded-[12px] bg-sheet px-3 py-1.5 text-meta text-ink-2">Drop to {target.label.replace("{to}", col.label).toLowerCase()}</p>}
                <ul className="flex-1 space-y-2">
                  {list.map((c) => {
                    const next = movesOf(c);
                    return (
                      <li
                        key={c.id}
                        draggable={next.length > 0 && !pending}
                        onDragStart={(e) => {
                          e.dataTransfer.effectAllowed = "move";
                          e.dataTransfer.setData("text/plain", c.id);
                          setDragging(c);
                        }}
                        onDragEnd={() => {
                          setDragging(null);
                          setOver(null);
                        }}
                        className={`group relative rounded-[14px] border border-rule bg-sheet px-3 py-2.5 transition hover:border-hema ${c.late ? "border-t-2 border-t-danger" : ""} ${
                          next.length ? "cursor-grab active:cursor-grabbing" : ""
                        } ${dragging?.id === c.id ? "opacity-50" : ""}`}
                      >
                        <p className="flex items-start justify-between gap-2">
                          <Link href={c.href} draggable={false} className="min-w-0 truncate text-sm font-medium text-ink after:absolute after:inset-0">
                            {c.title}
                          </Link>
                          {c.flag && <span className="shrink-0">{c.flag}</span>}
                        </p>
                        {c.sub && <p className="truncate text-meta text-ink-3">{c.sub}</p>}
                        {(c.value || c.when) && (
                          <p className="mt-1.5 flex items-baseline justify-between gap-2 text-meta">
                            <span className="truncate font-semibold text-ink">{c.value}</span>
                            <span className={`shrink-0 ${c.late ? "font-semibold text-danger" : "text-ink-3"}`}>{c.when}</span>
                          </p>
                        )}
                        {c.meta && <p className="mt-0.5 truncate text-meta text-ink-3">{c.meta}</p>}
                        {next.length > 0 && (
                          // The same moves without dragging: for a keyboard, and a phone.
                          <Dropdown
                            trigger={["click"]}
                            menu={{
                              items: next.map((m) => ({ key: m.to, label: m.label.replace("{to}", label(m.to)) + (m.label.includes("{to}") ? "" : ` → ${label(m.to)}`) })),
                              onClick: ({ key }) => take(c, next.find((m) => m.to === key)!),
                            }}
                          >
                            <button
                              type="button"
                              aria-label={`Move ${c.title}`}
                              className="absolute right-1.5 bottom-1.5 z-10 grid size-6 place-items-center rounded-full bg-sheet text-ink-3 opacity-0 group-hover:opacity-100 hover:bg-bench hover:text-ink focus-visible:opacity-100 max-lg:opacity-100"
                            >
                              <MoreHorizontal className="size-4" aria-hidden />
                            </button>
                          </Dropdown>
                        )}
                      </li>
                    );
                  })}
                </ul>
                {list.length === 0 && !target && <p className="rounded-[14px] border border-dashed border-rule-strong px-3 py-6 text-center text-meta text-ink-3">{col.hint ?? "Nothing here"}</p>}
                {more?.[col.key] && (
                  <Link href={more[col.key].href} className="mt-2 px-1.5 text-meta text-ink-2 hover:text-ink hover:underline">
                    {more[col.key].label}
                  </Link>
                )}
              </section>
            );
          })}
        </div>
      </div>
      <Modal
        open={asking !== null}
        title={asking?.move.confirm}
        okText={asking?.move.label.replace("{to}", asking ? label(asking.move.to) : "")}
        cancelText="Not now"
        onOk={() => asking && take(asking.card, asking.move, true)}
        onCancel={() => setAsking(null)}
      />
    </>
  );
}
