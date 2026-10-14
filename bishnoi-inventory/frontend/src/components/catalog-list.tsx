"use client";

import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { FormError, Input, Select } from "@/src/platform/ui/field";
import { Empty } from "@/src/platform/ui/sheet";
import { deleteCatalogItem, saveCatalogItem } from "../actions/inventory";

export type CatalogItem = { key: string; name: string; code?: string; parentId?: string | null; path?: string; isActive: boolean; count: number; childCount?: number };
type Kind = "categories" | "brands" | "units";

const WORDS: Record<Kind, { one: string; hint: string }> = {
  categories: { one: "category", hint: "Nest categories to build a hierarchy, for example Medical Supplies › Syringes." },
  brands: { one: "brand", hint: "The manufacturer or brand name." },
  units: { one: "unit", hint: "A short code (box) and a name (Box). Quantities are recorded in whole units." },
};

type Draft = { name: string; code: string; parentId: string };

/** A short list kept in place: add a row, rename one, switch it off, or delete one nothing uses. */
export function CatalogList({ kind, items, canEdit, canDelete }: { kind: Kind; items: CatalogItem[]; canEdit: boolean; canDelete: boolean }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>({ name: "", code: "", parentId: "" });
  const [error, setError] = useState<string | null>(null);
  const w = WORDS[kind];

  function open(item: CatalogItem | null) {
    setEditing(item?.key ?? "new");
    setDraft({ name: item?.name ?? "", code: item?.code ?? "", parentId: item?.parentId ?? "" });
    setError(null);
  }

  function run(work: () => Promise<{ ok: true } | { ok: false; error: string; fields?: Record<string, string> }>, done: string) {
    start(async () => {
      const result = await work();
      if (!result.ok) {
        setError(Object.values(result.fields ?? {})[0] ?? result.error);
        return;
      }
      toast.success(done);
      setEditing(null);
      setError(null);
      router.refresh();
    });
  }

  function save() {
    const isNew = editing === "new";
    const input: Record<string, unknown> = { name: draft.name.trim() };
    if (kind === "units" && isNew) input.code = draft.code.trim().toLowerCase();
    if (kind === "categories") input.parentId = draft.parentId || null;
    run(async () => {
      const r = await saveCatalogItem(kind, isNew ? null : editing, input);
      return r.ok ? { ok: true } : r;
    }, isNew ? `${draft.name.trim()} added` : "Saved");
  }

  const form = (
    <div className="flex flex-wrap items-end gap-3 bg-bench/50 px-5 py-3">
      {kind === "units" && editing === "new" && (
        <div className="w-28">
          <Input aria-label="Code" placeholder="box" value={draft.code} onChange={(e) => setDraft({ ...draft, code: e.target.value })} autoFocus />
        </div>
      )}
      <div className="min-w-48 flex-1">
        <Input aria-label="Name" placeholder={kind === "units" ? "Box" : "Name"} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} autoFocus={kind !== "units" || editing !== "new"} />
      </div>
      {kind === "categories" && (
        <div className="min-w-48">
          <Select aria-label="Parent category" value={draft.parentId} onChange={(e) => setDraft({ ...draft, parentId: e.target.value })}>
            <option value="">None (top level)</option>
            {items.filter((c) => c.key !== editing).map((c) => <option key={c.key} value={c.key}>Inside {c.path}</option>)}
          </Select>
        </div>
      )}
      <Button size="sm" variant="primary" loading={pending} icon={<Check className="size-4" aria-hidden />} onClick={save}>
        {editing === "new" ? `Add ${w.one}` : "Save"}
      </Button>
      <Button size="sm" variant="quiet" icon={<X className="size-4" aria-hidden />} onClick={() => setEditing(null)}>
        Cancel
      </Button>
      {error && <div className="w-full"><FormError message={error} /></div>}
    </div>
  );

  return (
    <div>
      <p className="px-5 pt-4 pb-2 text-meta text-ink-3">{w.hint}</p>
      {items.length === 0 && editing !== "new" ? (
        <Empty title={`No ${kind}`} icon="lists" />
      ) : (
        <ul className="divide-y divide-rule border-t border-rule">
          {items.map((item) =>
            editing === item.key ? (
              <li key={item.key}>{form}</li>
            ) : (
              <li key={item.key} className="flex items-center justify-between gap-3 px-5 py-2.5">
                <span className="min-w-0 text-sm">
                  <span className={`font-semibold ${item.isActive ? "text-ink" : "text-ink-3 line-through"}`}>{kind === "categories" ? item.path : item.name}</span>
                  {item.code && <span className="ml-2 font-mono text-meta text-ink-3">{item.code}</span>}
                  <span className="block text-meta text-ink-3">
                    {item.count} product{item.count === 1 ? "" : "s"}
                    {item.childCount ? ` · ${item.childCount} inside` : ""}
                    {!item.isActive && " · switched off"}
                  </span>
                </span>
                {canEdit && (
                  <span className="flex shrink-0 items-center gap-1">
                    <Button size="sm" variant="quiet" onClick={() => run(async () => { const r = await saveCatalogItem(kind, item.key, { isActive: !item.isActive }); return r.ok ? { ok: true } : r; }, item.isActive ? `${item.name} deactivated` : `${item.name} activated`)}>
                      {item.isActive ? "Deactivate" : "Activate"}
                    </Button>
                    <button type="button" title={`Rename ${item.name}`} onClick={() => open(item)} className="rounded-md p-1.5 text-ink-3 hover:bg-bench hover:text-ink">
                      <Pencil className="size-4" aria-hidden />
                    </button>
                    {canDelete && item.count === 0 && !item.childCount && (
                      <button type="button" title={`Delete ${item.name}`} onClick={() => run(async () => { const r = await deleteCatalogItem(kind, item.key); return r.ok ? { ok: true } : r; }, `${item.name} deleted`)} className="rounded-md p-1.5 text-ink-3 hover:bg-bench hover:text-danger">
                        <Trash2 className="size-4" aria-hidden />
                      </button>
                    )}
                  </span>
                )}
              </li>
            ),
          )}
          {editing === "new" && <li>{form}</li>}
        </ul>
      )}
      {canEdit && editing !== "new" && (
        <div className="px-5 py-3">
          <Button size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => open(null)}>
            Add {w.one}
          </Button>
        </div>
      )}
      {error && editing === null && <div className="px-5 pb-3"><FormError message={error} /></div>}
    </div>
  );
}
