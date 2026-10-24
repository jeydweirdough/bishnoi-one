"use client";

import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/pharmacy/platform/ui/button";
import { ConfirmButton } from "@/src/modules/pharmacy/platform/ui/confirm";
import { CellInput, FormError } from "@/src/modules/pharmacy/platform/ui/field";
import { Empty } from "@/src/modules/pharmacy/platform/ui/sheet";
import { deleteBrand, deleteCategory, saveBrand, saveCategory } from "@/src/modules/pharmacy/actions/pharmacy";

type Row = { id: string; name: string; extra: string | null; isActive: boolean; medicineCount: number };

/**
 * Categories or brands: a short list kept by hand. Each row's own controls
 * (rename, switch off, delete) sit on that row, naming what they act on.
 */
export function NamedList({ kind, rows, canCreate, canEdit, canDelete }: { kind: "category" | "brand"; rows: Row[]; canCreate: boolean; canEdit: boolean; canDelete: boolean }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [extra, setExtra] = useState("");
  const [error, setError] = useState<string | null>(null);
  const extraLabel = kind === "brand" ? "Manufacturer" : "Description";
  const save = kind === "brand" ? saveBrand : saveCategory;
  const remove = kind === "brand" ? deleteBrand : deleteCategory;

  function begin(row: Row | null) {
    setEditing(row?.id ?? "new");
    setName(row?.name ?? "");
    setExtra(row?.extra ?? "");
    setError(null);
  }

  function commit(row: Row | null, value: { name: string; extra: string | null; isActive: boolean }) {
    start(async () => {
      const result = await save(row?.id ?? null, { name: value.name.trim(), manufacturer: value.extra, description: value.extra, isActive: value.isActive });
      if (result.ok) {
        setEditing(null);
        setError(null);
        toast.success(row ? "Saved" : `${kind === "brand" ? "Brand" : "Category"} added`, { description: result.data.name });
        router.refresh();
        return;
      }
      setError(result.fields?.name ?? result.error);
    });
  }

  const form = (row: Row | null) => (
    <div className="flex flex-wrap items-center gap-2 px-5 py-2.5">
      <CellInput className="w-56 !text-left" aria-label="Name" value={name} onChange={(e) => setName(e.target.value)} autoFocus placeholder="Name" />
      <CellInput className="w-64 !text-left" aria-label={extraLabel} value={extra} onChange={(e) => setExtra(e.target.value)} placeholder={`${extraLabel} (optional)`} />
      <Button size="sm" variant="primary" loading={pending} onClick={() => commit(row, { name, extra: extra.trim() || null, isActive: row?.isActive ?? true })} icon={<Check className="size-4" aria-hidden />}>
        Save
      </Button>
      <Button size="sm" variant="quiet" onClick={() => setEditing(null)} icon={<X className="size-4" aria-hidden />}>
        Cancel
      </Button>
    </div>
  );

  return (
    <div>
      {rows.length === 0 && editing !== "new" ? (
        <Empty icon="lists" title={`No ${kind === "brand" ? "brands" : "categories"} yet`} />
      ) : (
        <ul className="divide-y divide-rule">
          {rows.map((row) =>
            editing === row.id ? (
              <li key={row.id}>{form(row)}</li>
            ) : (
              <li key={row.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
                <div className="flex min-w-0 items-center gap-1.5">
                  <span className={`font-semibold ${row.isActive ? "text-ink" : "text-ink-3"}`}>{row.name}</span>
                  {canEdit && (
                    <button suppressHydrationWarning type="button" onClick={() => begin(row)} title={`Rename ${row.name}`} aria-label={`Rename ${row.name}`} className="rounded-[3px] p-1 text-ink-3 hover:bg-hema-tint hover:text-hema">
                      <Pencil className="size-3.5" aria-hidden />
                    </button>
                  )}
                  {canDelete && row.medicineCount === 0 && (
                    <ConfirmButton
                      label=""
                      icon={<Trash2 className="size-3.5" aria-hidden />}
                      triggerVariant="quiet"
                      triggerSize="sm"
                      triggerClassName="!h-7 !px-1.5 text-ink-3"
                      triggerTitle={`Delete ${row.name}`}
                      title={`Delete ${row.name}?`}
                      confirmLabel="Delete"
                      onConfirm={async () => {
                        const r = await remove(row.id);
                        if (!r.ok) toast.error(r.error);
                        return r.ok;
                      }}
                    />
                  )}
                  {row.extra && <span className="ml-1 truncate text-meta text-ink-3">{row.extra}</span>}
                </div>
                <div className="flex items-center gap-3 text-meta text-ink-3">
                  <span>
                    {row.medicineCount} medicine{row.medicineCount === 1 ? "" : "s"}
                  </span>
                  {canEdit && (
                    <button suppressHydrationWarning type="button" className="font-semibold text-hema hover:underline" onClick={() => commit(row, { name: row.name, extra: row.extra, isActive: !row.isActive })}>
                      {row.isActive ? "Switch off" : "Switch on"}
                    </button>
                  )}
                </div>
              </li>
            ),
          )}
          {editing === "new" && <li>{form(null)}</li>}
        </ul>
      )}
      <FormError message={error} />
      {canCreate && editing !== "new" && (
        <div className="border-t border-rule px-5 py-3">
          <Button size="sm" onClick={() => begin(null)} icon={<Plus className="size-4" aria-hidden />}>
            Add {kind}
          </Button>
        </div>
      )}
    </div>
  );
}
