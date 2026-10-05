"use client";

import { Plus, X } from "lucide-react";
import { useId, useState } from "react";

/** One chip: a word in a small square-cornered box, with × when it can be removed. */
export function Chip({ children, onRemove, removeLabel }: { children: string; onRemove?: () => void; removeLabel?: string }) {
  return (
    <span className="inline-flex h-7 items-center gap-1 rounded-[6px] border border-rule-strong bg-sheet pr-1 pl-2.5 text-sm text-ink">
      {children}
      {onRemove ? (
        <button type="button" onClick={onRemove} className="rounded-[4px] p-1 text-ink-3 hover:bg-bench hover:text-danger" aria-label={removeLabel ?? `Remove ${children}`}>
          <X className="size-3" aria-hidden />
        </button>
      ) : (
        <span className="w-2" />
      )}
    </span>
  );
}

/** A list of short names, added one at a time as chips: type, then Enter or Add. */
export function ChipsInput({
  label,
  value,
  onChange,
  placeholder,
  error,
  max = 20,
  optional = true,
}: {
  label: string;
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  error?: string;
  max?: number;
  optional?: boolean;
}) {
  const id = useId();
  const [text, setText] = useState("");
  const [note, setNote] = useState<string | null>(null);

  function add() {
    const name = text.trim();
    if (!name) return;
    if (value.some((v) => v.toLowerCase() === name.toLowerCase())) return setNote(`${name} is already there.`);
    if (value.length >= max) return setNote(`At most ${max}.`);
    onChange([...value, name]);
    setText("");
    setNote(null);
  }

  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-meta font-medium text-ink-2">
        {label} {optional && <span className="font-normal text-ink-3">(optional)</span>}
      </label>
      <div className="flex flex-wrap items-center gap-1.5">
        {value.map((v) => (
          <Chip key={v} onRemove={() => onChange(value.filter((x) => x !== v))}>
            {v}
          </Chip>
        ))}
        <span className="inline-flex items-center gap-1">
          <input
            id={id}
            value={text}
            maxLength={120}
            onChange={(e) => {
              setText(e.target.value);
              setNote(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault(); // add the chip, don't send the form
                add();
              } else if (e.key === "Backspace" && !text && value.length) {
                onChange(value.slice(0, -1));
              }
            }}
            placeholder={placeholder}
            className="h-8 w-44 border-0 border-b border-control bg-transparent px-0 text-sm focus:border-hema focus:outline-none"
          />
          <button
            type="button"
            onClick={add}
            disabled={!text.trim()}
            className="inline-flex h-7 items-center gap-1 rounded-[6px] border border-dashed border-rule-strong px-2.5 text-meta text-ink-2 hover:border-hema hover:text-ink disabled:opacity-40"
          >
            <Plus className="size-3" aria-hidden />
            Add
          </button>
        </span>
      </div>
      {(error || note) && <p className="mt-1 text-meta text-danger">{error ?? note}</p>}
    </div>
  );
}
