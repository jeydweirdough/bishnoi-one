"use client";

import { IconButton } from "./button";
import { ArrowDown, ArrowUp, Plus, X } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "../ui/button";
import { Field, FormError, Input } from "../ui/field";
import { Icon, listIcon, type IconName } from "../ui/icons";
import { SectionTitle, Sheet } from "../ui/sheet";
import { plural } from "../lib/format";
import { SaveBar } from "./pick-list";

// One pick-list, edited the same way wherever a company keeps one: name each
// choice, put them in the order people should read them, switch off the ones
// you've stopped using. Settings → Orders and Settings → Lists both use this,
// so an admin only ever learns it once.

export type ListRow = { id: string; code?: string; name: string; icon: string | null; isActive: boolean };

/** What a saved list looks like on the way back to the API. A choice with no code is a new one. */
export type ListRowInput = { code?: string; name: string; icon: string | null; isActive: boolean };

/** What every one of these saves returns; the shape `attempt()` gives back. */
type Saved = { ok: true } | { ok: false; error: string; fields?: Record<string, string> };

let counter = 0;
const newId = () => `new-${++counter}`;

export function listRows(items: { code: string; name: string; icon?: string | null; isActive: boolean }[]): ListRow[] {
  return items.map((i) => ({ id: i.code, code: i.code, name: i.name, icon: i.icon ?? null, isActive: i.isActive }));
}

/** The one line under a list's name in the picker, so the picker itself answers most questions. */
export function listDetail(items: { isActive: boolean }[]): string {
  const off = items.filter((i) => !i.isActive).length;
  return items.length === 0 ? "Empty" : off ? `${items.length - off} on · ${off} off` : plural(items.length, "choice");
}


/** The shared icon button (src/platform/ui/button.tsx), for this kit's callers. */
export { IconButton };

export function moved<T>(rows: T[], from: number, by: number): T[] {
  const next = [...rows];
  const [row] = next.splice(from, 1);
  next.splice(from + by, 0, row);
  return next;
}

/** The pictures on offer for one choice. Picking one shows at once, and saves with the rest. */
function IconRow({
  choices,
  value,
  onPick,
}: {
  choices: readonly { name: IconName; label: string }[];
  value: IconName;
  onPick: (icon: IconName) => void;
}) {
  return (
    <div className="mt-1 flex animate-reshape flex-wrap gap-1 pl-8" role="group" aria-label="Icon">
      {choices.map(({ name, label }) => (
        <button suppressHydrationWarning
          key={name}
          type="button"
          aria-pressed={value === name}
          aria-label={label}
          title={label}
          onClick={() => onPick(name)}
          className={`inline-flex size-7 items-center justify-center rounded-md border ${
            value === name ? "border-hema bg-hema-tint text-ink" : "border-rule text-ink-3 hover:border-control"
          }`}
        >
          <Icon name={name} className="size-4" />
        </button>
      ))}
    </div>
  );
}

export function ListEditor({
  icon,
  label,
  hint,
  note,
  savedNote,
  icons,
  required = false,
  rows,
  dirty,
  setRows,
  onSave,
}: {
  icon: IconName;
  label: string;
  hint: string;
  /** The quiet line saying what switching a choice off does to the records that carry it. */
  note: string;
  /** What changes for everyone else once it's saved. */
  savedNote: string;
  /** Present when this list's choices carry a picture. */
  icons?: readonly { name: IconName; label: string }[];
  /** A list records can't be made without: it must keep at least one choice switched on. */
  required?: boolean;
  rows: ListRow[];
  dirty: boolean;
  setRows: (rows: ListRow[] | undefined) => void;
  onSave: (items: ListRowInput[]) => Promise<Saved>;
}) {
  const [adding, setAdding] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();
  // One choice's pictures at a time: a dozen buttons under every row would bury the names.
  const [picking, setPicking] = useState<string | null>(null);

  const change = (i: number, patch: Partial<ListRow>) => setRows(rows.map((r, n) => (n === i ? { ...r, ...patch } : r)));

  function add() {
    const name = adding.trim();
    if (!name) return;
    if (rows.some((r) => r.name.trim().toLowerCase() === name.toLowerCase())) {
      setErrors({ adding: "Already in the list." });
      return;
    }
    setRows([...rows, { id: newId(), name, icon: icons ? icons[0].name : null, isActive: true }]);
    setAdding("");
    setErrors({});
  }

  function save() {
    const found: Record<string, string> = {};
    const seen = new Set<string>();
    rows.forEach((r, i) => {
      const name = r.name.trim().toLowerCase();
      if (!name) found[`items.${i}.name`] = "Give it a name, or remove it.";
      else if (seen.has(name)) found[`items.${i}.name`] = "Already in the list.";
      seen.add(name);
    });
    setErrors(found);
    if (Object.keys(found).length) return;
    if (required && !rows.some((r) => r.isActive)) {
      return setError(`Leave at least one ${label.toLowerCase().replace(/s$/, "")} active: records can't be created without one.`);
    }
    start(async () => {
      const result = await onSave(rows.map((r) => ({ code: r.code, name: r.name.trim(), icon: r.icon, isActive: r.isActive })));
      if (!result.ok) {
        setErrors(result.fields ?? {});
        return setError(result.error);
      }
      setError(null);
      setRows(undefined);
      setPicking(null);
      toast.success(`${label} saved`, { description: savedNote });
    });
  }

  return (
    <Sheet className="px-5 pt-4 pb-5">
      <SectionTitle icon={icon}>{label}</SectionTitle>
      <p className="text-meta text-ink-3">
        {hint} {note}
      </p>
      {rows.length === 0 ? (
        <p className="mt-4 text-sm text-ink-2">No options yet. Add the first option below.</p>
      ) : (
        <ol className="mt-3 divide-y divide-rule border-y border-rule">
          {rows.map((row, i) => {
            const problem = errors[`items.${i}.name`];
            const open = picking === row.id;
            return (
              <li key={row.id} className="py-1.5">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="w-6 shrink-0 text-right text-meta text-ink-3 tabular-nums">{i + 1}</span>
                  {icons && (
                    <IconButton
                      label={`Picture for ${row.name || "this choice"}`}
                      pressed={open}
                      onClick={() => setPicking(open ? null : row.id)}
                    >
                      <Icon name={listIcon(row)} className="size-4" />
                    </IconButton>
                  )}
                  {/* On a phone the name takes the line and its controls wrap beneath. */}
                  <div className="min-w-0 flex-1 basis-52">
                    <Input
                      aria-label={`${label}, choice ${i + 1}`}
                      aria-invalid={problem ? true : undefined}
                      value={row.name}
                      maxLength={120}
                      onChange={(e) => change(i, { name: e.target.value })}
                      className={row.isActive ? "" : "text-ink-3 line-through decoration-rule-strong"}
                    />
                  </div>
                  <span className="ml-auto flex items-center">
                    <label className="flex h-8 shrink-0 cursor-pointer items-center gap-1.5 px-1 text-meta text-ink-2">
                      <input suppressHydrationWarning
                        type="checkbox"
                        checked={row.isActive}
                        onChange={(e) => change(i, { isActive: e.target.checked })}
                        className="size-4 accent-hema"
                      />
                      On
                    </label>
                    <IconButton label={`Move ${row.name || "this"} up`} disabled={i === 0} onClick={() => setRows(moved(rows, i, -1))}>
                      <ArrowUp className="size-4" aria-hidden />
                    </IconButton>
                    <IconButton
                      label={`Move ${row.name || "this"} down`}
                      disabled={i === rows.length - 1}
                      onClick={() => setRows(moved(rows, i, 1))}
                    >
                      <ArrowDown className="size-4" aria-hidden />
                    </IconButton>
                    <IconButton label={`Remove ${row.name || "this"}`} onClick={() => setRows(rows.filter((_, n) => n !== i))}>
                      <X className="size-4" aria-hidden />
                    </IconButton>
                  </span>
                </div>
                {icons && open && <IconRow choices={icons} value={listIcon(row)} onPick={(name) => change(i, { icon: name })} />}
                {problem && <p className="mt-1 pl-8 text-meta text-danger">{problem}</p>}
              </li>
            );
          })}
        </ol>
      )}
      <form
        className="mt-4 flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          add();
        }}
      >
        <Field label="Add a choice" className="flex-1" error={errors.adding}>
          {(p) => <Input {...p} value={adding} maxLength={120} onChange={(e) => setAdding(e.target.value)} />}
        </Field>
        <Button type="submit" size="sm" icon={<Plus className="size-4" aria-hidden />} disabled={!adding.trim()}>
          Add
        </Button>
      </form>
      {dirty && (
        <SaveBar
          what={`Unsaved changes to ${label.toLowerCase()}`}
          saving={saving}
          onSave={save}
          onDiscard={() => {
            setRows(undefined);
            setErrors({});
            setError(null);
            setPicking(null);
          }}
          error={<FormError message={error} />}
        />
      )}
    </Sheet>
  );
}
