"use client";

import { Segmented } from "antd";
import { useState, type ReactNode } from "react";

/**
 * Two or three parts of one card, one shown at a time (Due now / Coming up),
 * as Ant Design's segmented control: the card keeps one height however long
 * either list is. The parts are drawn on the server and handed over whole;
 * only which one shows lives here. Starts on the first part that has anything.
 */
export function PanelTabs({ tabs, label }: { tabs: { value: string; label: string; count?: number; content: ReactNode }[]; label: string }) {
  const first = tabs.find((t) => t.count !== 0) ?? tabs[0];
  const [current, setCurrent] = useState(first.value);
  const shown = tabs.find((t) => t.value === current) ?? first;
  return (
    <div>
      <Segmented<string>
        block
        size="small"
        aria-label={label}
        value={current}
        onChange={setCurrent}
        options={tabs.map((t) => ({
          value: t.value,
          label: (
            <span className="inline-flex items-center gap-1.5">
              {t.label}
              {t.count !== undefined && <span className="tabular-nums opacity-60">{t.count}</span>}
            </span>
          ),
        }))}
      />
      <div className="mt-2" role="tabpanel" aria-label={shown.label}>
        {shown.content}
      </div>
    </div>
  );
}
