"use client";

import type { ReactNode } from "react";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Select } from "@/src/modules/finance/platform/ui/field";
import type { IconName } from "@/src/modules/finance/platform/ui/icons";
import { SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";

export type PickItem = {
  key: string;
  label: string;
  /** One line under the name: what's set, so the list itself answers most questions. */
  detail?: string;
  unsaved?: boolean;
  group?: string;
};

/**
 * Settings pages show one thing at a time: pick a role, a division, then see
 * only its choices. On wide screens the list sits beside what it picks; on a
 * phone it folds into a single select above it.
 */
export function PickList({
  title,
  items,
  selected,
  onSelect,
  footer,
  icon,
}: {
  title: string;
  icon?: IconName;
  items: PickItem[];
  selected: string;
  onSelect: (key: string) => void;
  footer?: ReactNode;
}) {
  const groups = [...new Set(items.map((i) => i.group ?? ""))];
  return (
    <>
      <div className="lg:hidden">
        <label className="mb-1 block text-meta font-medium text-ink-2" htmlFor={`pick-${title}`}>
          {title}
        </label>
        <Select id={`pick-${title}`} value={selected} onChange={(e) => onSelect(e.target.value)}>
          {items.map((i) => (
            <option key={i.key} value={i.key}>
              {i.label}
              {i.unsaved ? " · unsaved" : ""}
            </option>
          ))}
        </Select>
        {footer}
      </div>

      <Sheet className="hidden px-3 pt-4 pb-3 lg:block">
        <div className="px-2">
          <SectionTitle icon={icon}>{title}</SectionTitle>
        </div>
        {groups.map((group) => (
          <div key={group} className="mt-1 first:mt-0">
            {group && <p className="px-3 pt-2 pb-1 text-meta font-semibold text-ink-3">{group}</p>}
            <ul className="space-y-0.5" role="list">
              {items
                .filter((i) => (i.group ?? "") === group)
                .map((i) => {
                  const on = i.key === selected;
                  return (
                    <li key={i.key}>
                      <button
                        type="button"
                        onClick={() => onSelect(i.key)}
                        aria-pressed={on}
                        className={`w-full rounded-[3px] px-3 py-2 text-left ${on ? "bg-hema-tint" : "hover:bg-bench/60"}`}
                      >
                        <span className={`block text-sm ${on ? "font-semibold text-hema" : "text-ink"}`}>
                          {i.label}
                          {i.unsaved && <span className="ml-1.5 text-meta font-normal text-ink-3">· unsaved</span>}
                        </span>
                        {i.detail && <span className="block truncate text-meta text-ink-3">{i.detail}</span>}
                      </button>
                    </li>
                  );
                })}
            </ul>
          </div>
        ))}
        {footer}
      </Sheet>
    </>
  );
}

/** The sticky "unsaved changes" bar every settings editor ends with. */
export function SaveBar({
  what,
  saving,
  onSave,
  onDiscard,
  error,
  saveLabel = "Save changes",
}: {
  what: ReactNode;
  saving: boolean;
  onSave: () => void;
  onDiscard: () => void;
  error?: ReactNode;
  saveLabel?: string;
}) {
  return (
    <div className="sticky bottom-3 z-10 mt-4 animate-rise space-y-2 rounded-[3px] bg-sheet px-4 py-3 shadow-overlay">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm">{what}</span>
        <span className="flex gap-2">
          <Button size="sm" variant="quiet" onClick={onDiscard} disabled={saving}>
            Discard
          </Button>
          <Button size="sm" variant="primary" onClick={onSave} loading={saving}>
            {saveLabel}
          </Button>
        </span>
      </div>
      {error}
    </div>
  );
}
