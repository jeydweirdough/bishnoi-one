"use client";

import { IconButton } from "@/src/platform/ui/button";
import { Dropdown } from "antd";
import { AlarmClock, Cake, ChevronLeft, ChevronRight, CircleAlert, FileClock, Gauge, MoreHorizontal, ShieldAlert, UserRoundPen, Moon } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState, useTransition, type ReactNode } from "react";
import { toast } from "sonner";
import { Empty } from "@/src/platform/ui/sheet";
import { putAside, type Prompt } from "../actions/attention";

/** How many show at once on a home page; the rest are a swipe (or a dot) away. */
const PER_PAGE = 1;

const ICONS: Record<string, ReactNode> = {
  overdue: <AlarmClock className="size-4" aria-hidden />,
  occasion: <Cake className="size-4" aria-hidden />,
  quiet: <Moon className="size-4" aria-hidden />,
  quote: <FileClock className="size-4" aria-hidden />,
  target: <Gauge className="size-4" aria-hidden />,
  clidp: <ShieldAlert className="size-4" aria-hidden />,
  profile: <UserRoundPen className="size-4" aria-hidden />,
};

/** The prompts left, and putting one aside (for a week, or for good) with it gone at once. */
function usePrompts(prompts: Prompt[]) {
  const [gone, setGone] = useState<Set<string>>(new Set());
  const [, start] = useTransition();
  const left = prompts.filter((p) => !gone.has(p.key));
  function aside(p: Prompt, how: "snooze" | "dismiss") {
    setGone((g) => new Set(g).add(p.key));
    start(async () => {
      const r = await putAside(p.key, how);
      if (!r.ok) {
        toast.error(r.error);
        setGone((g) => {
          const next = new Set(g);
          next.delete(p.key);
          return next;
        });
      } else toast.success(how === "snooze" ? "Back in a week" : "Won't show again", { description: p.title });
    });
  }
  return { left, aside };
}

/** One thing to do: what, why, the one action, and putting it aside. */
function PromptRow({ p, aside }: { p: Prompt; aside: (p: Prompt, how: "snooze" | "dismiss") => void }) {
  return (
    <li className="flex items-start gap-3.5 py-3.5">
      <span className="grid size-10 shrink-0 place-items-center rounded-full border-[1.5px] border-ink bg-sheet text-ink">{ICONS[p.kind] ?? <CircleAlert className="size-4" aria-hidden />}</span>
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-ink">{p.title}</p>
        <p className="text-meta text-ink-3">{p.reason}</p>
      </div>
      <Link href={p.href} className="shrink-0 self-center rounded-full border border-ink bg-sheet px-3.5 py-1 text-sm font-medium text-ink hover:bg-sage/40">
        {p.action}
      </Link>
      <Dropdown
        trigger={["click"]}
        menu={{
          items: [
            { key: "snooze", label: "Remind me in a week" },
            { key: "dismiss", label: "Don't show this again" },
          ],
          onClick: ({ key }) => aside(p, key as "snooze" | "dismiss"),
        }}
      >
        <IconButton tone="soft" className="self-center" label={`Put aside: ${p.title}`}>
          <MoreHorizontal className="size-4" aria-hidden />
        </IconButton>
      </Dropdown>
    </li>
  );
}

/**
 * "Needs your attention" on a home page: one at a time, most pressing first.
 * The rest are pages side by side: swipe (or scroll) across, or press a dot or an
 * arrow; "See all" opens every one as a list on its own page.
 */
export function AttentionCard({ prompts }: { prompts: Prompt[] }) {
  const { left, aside } = usePrompts(prompts);
  const track = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState(0);
  const pages = Array.from({ length: Math.ceil(left.length / PER_PAGE) }, (_, i) => left.slice(i * PER_PAGE, (i + 1) * PER_PAGE));
  // A page put aside away: stay on a page that's still there.
  useEffect(() => {
    if (page > pages.length - 1) go(Math.max(0, pages.length - 1));
  }, [pages.length]); // eslint-disable-line react-hooks/exhaustive-deps
  if (left.length === 0) return null;

  function go(n: number) {
    const el = track.current;
    if (!el) return;
    el.scrollTo({ left: n * el.clientWidth, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    setPage(n);
  }

  return (
    <section aria-labelledby="attention" className="mb-5 rounded-[28px] bg-mint">
      <div className="flex items-center justify-between gap-3 px-6 pt-5 pb-1">
        <h2 id="attention" className="text-heading text-ink">
          Needs your attention
        </h2>
        <span className="flex items-center gap-3">
          <Link href="/attention" className="text-meta font-medium text-ink hover:underline">
            See all
          </Link>
          <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-full border-[1.5px] border-ink bg-sheet px-2 text-meta font-semibold text-ink" aria-label={left.length === 1 ? "1 thing" : `${left.length} things`}>
            {left.length}
          </span>
        </span>
      </div>

      {/* The pages, side by side: a swipe or a trackpad scroll moves across, each stopping in place. */}
      <div
        ref={track}
        onScroll={(e) => {
          const el = e.currentTarget;
          const n = Math.round(el.scrollLeft / Math.max(1, el.clientWidth));
          if (n !== page) setPage(n);
        }}
        className="flex snap-x snap-mandatory overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        aria-roledescription="carousel"
      >
        {pages.map((rows, i) => (
          <ul key={i} className="w-full shrink-0 snap-start divide-y divide-mint-2 px-6" aria-label={`Page ${i + 1} of ${pages.length}`} aria-hidden={i !== page}>
            {rows.map((p) => (
              <PromptRow key={p.key} p={p} aside={aside} />
            ))}
          </ul>
        ))}
      </div>

      {pages.length > 1 ? (
        <div className="flex items-center justify-center gap-3 px-6 pt-1 pb-4">
          <IconButton onClick={() => go(Math.max(0, page - 1))} disabled={page === 0} tone="soft" size="sm" label="The ones before">
            <ChevronLeft className="size-4" aria-hidden />
          </IconButton>
          <span className="flex items-center gap-1.5">
            {pages.map((_, i) => (
              <button
                key={i}
                type="button"
                onClick={() => go(i)}
                className={`h-2 rounded-full transition-all ${i === page ? "w-5 bg-ink" : "w-2 bg-ink/25 hover:bg-ink/45"}`}
                aria-label={`Page ${i + 1} of ${pages.length}`}
                aria-current={i === page ? "true" : undefined}
              />
            ))}
          </span>
          <IconButton onClick={() => go(Math.min(pages.length - 1, page + 1))} disabled={page === pages.length - 1} tone="soft" size="sm" label="The next ones">
            <ChevronRight className="size-4" aria-hidden />
          </IconButton>
        </div>
      ) : (
        <div className="pb-2" />
      )}
    </section>
  );
}

/** Every prompt, as one list: the "See all" page. */
export function AttentionList({ prompts }: { prompts: Prompt[] }) {
  const { left, aside } = usePrompts(prompts);
  if (left.length === 0) {
    return (
      <Empty icon="inbox" title="Nothing needs you right now">
        Overdue follow-ups, quotes waiting, quiet customers and thin profiles show up here as they come.
      </Empty>
    );
  }
  return (
    <ul className="divide-y divide-rule px-5">
      {left.map((p) => (
        <PromptRow key={p.key} p={p} aside={aside} />
      ))}
    </ul>
  );
}
