"use client";

import { Dropdown } from "antd";
import { AlarmClock, Cake, CircleAlert, FileClock, Gauge, MoreHorizontal, ShieldAlert, UserRoundPen, Moon } from "lucide-react";
import Link from "next/link";
import { useState, useTransition, type ReactNode } from "react";
import { toast } from "sonner";
import { putAside, type Prompt } from "../actions/attention";

const SHOWN = 5;

const ICONS: Record<string, ReactNode> = {
  overdue: <AlarmClock className="size-4" aria-hidden />,
  occasion: <Cake className="size-4" aria-hidden />,
  quiet: <Moon className="size-4" aria-hidden />,
  quote: <FileClock className="size-4" aria-hidden />,
  target: <Gauge className="size-4" aria-hidden />,
  clidp: <ShieldAlert className="size-4" aria-hidden />,
  profile: <UserRoundPen className="size-4" aria-hidden />,
};

/**
 * "Needs your attention": the few things worth doing today, most pressing
 * first, each with why and one thing to do. Five show; the rest wait behind
 * "See all". Each can be put aside for a week, or for good.
 */
export function AttentionCard({ prompts }: { prompts: Prompt[] }) {
  const [gone, setGone] = useState<Set<string>>(new Set());
  const [all, setAll] = useState(false);
  const [, start] = useTransition();
  const left = prompts.filter((p) => !gone.has(p.key));
  if (left.length === 0) return null;
  const shown = all ? left : left.slice(0, SHOWN);

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
      }
    });
  }

  return (
    <section aria-labelledby="attention" className="mb-5 rounded-sheet border border-rule bg-sheet shadow-sheet">
      <div className="flex items-center justify-between gap-3 px-5 pt-4 pb-2">
        <h2 id="attention" className="flex items-center gap-2 text-heading text-ink">
          <CircleAlert className="size-[1.125rem] text-ink-3" aria-hidden />
          Needs your attention
        </h2>
        <span className="text-meta text-ink-3">{left.length === 1 ? "1 thing" : `${left.length} things`}</span>
      </div>
      <ul className="divide-y divide-rule">
        {shown.map((p) => (
          <li key={p.key} className="flex items-start gap-3 px-5 py-3">
            <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-bench text-ink-2">{ICONS[p.kind] ?? <CircleAlert className="size-4" aria-hidden />}</span>
            <div className="min-w-0 flex-1">
              <p className="font-medium text-ink">{p.title}</p>
              <p className="text-meta text-ink-3">{p.reason}</p>
            </div>
            <Link href={p.href} className="shrink-0 self-center rounded-[6px] border border-rule px-3 py-1 text-sm text-ink hover:border-ink-3">
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
              <button type="button" className="shrink-0 self-center rounded p-1 text-ink-3 hover:text-ink" aria-label={`Put aside: ${p.title}`}>
                <MoreHorizontal className="size-4" aria-hidden />
              </button>
            </Dropdown>
          </li>
        ))}
      </ul>
      {left.length > SHOWN && (
        <button type="button" onClick={() => setAll(!all)} className="w-full border-t border-rule px-5 py-2.5 text-left text-meta text-ink-2 hover:text-ink">
          {all ? "Show the top five" : `See all ${left.length}`}
        </button>
      )}
    </section>
  );
}
