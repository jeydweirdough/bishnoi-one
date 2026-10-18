"use client";

import { Collapse } from "antd";
import { useState, type ReactNode } from "react";

export type DetailSection = { title: string; items: [string, ReactNode][] };

const filled = (v: ReactNode) => v !== null && v !== undefined && v !== "";

/** One section's fields: label above value, so long labels never squeeze the value. Empty ones wait behind a click. */
function Fields({ items }: { items: [string, ReactNode][] }) {
  const [showEmpty, setShowEmpty] = useState(false);
  const shown = items.filter(([, v]) => filled(v));
  const empty = items.filter(([, v]) => !filled(v));
  return (
    <div>
      <dl className="space-y-3 text-sm">
        {[...shown, ...(showEmpty ? empty : [])].map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-meta text-ink-3">{label}</dt>
            <dd className="mt-0.5 break-words text-ink">{filled(value) ? value : <span className="text-ink-3">—</span>}</dd>
          </div>
        ))}
      </dl>
      {empty.length > 0 && (
        <button
          type="button"
          onClick={() => setShowEmpty(!showEmpty)}
          className={`text-meta text-ink-3 hover:text-ink hover:underline ${shown.length || showEmpty ? "mt-3" : ""}`}
        >
          {showEmpty ? "Hide empty" : `Show ${empty.length} empty`}
        </button>
      )}
    </div>
  );
}

/**
 * A customer's details, section by section as the form lays them out. A
 * section with something in it starts open; one with nothing starts closed.
 */
export function DetailSections({ sections }: { sections: DetailSection[] }) {
  const open = sections.map((s, i) => (s.items.some(([, v]) => filled(v)) ? String(i) : null)).filter((k): k is string => k !== null);
  return (
    <Collapse
      ghost
      size="small"
      defaultActiveKey={open}
      items={sections.map((s, i) => {
        const count = s.items.filter(([, v]) => filled(v)).length;
        return {
          key: String(i),
          label: <span className="font-medium text-ink">{s.title}</span>,
          extra: (
            <span className="text-meta text-ink-3">
              {count} of {s.items.length}
            </span>
          ),
          children: <Fields items={s.items} />,
        };
      })}
    />
  );
}
