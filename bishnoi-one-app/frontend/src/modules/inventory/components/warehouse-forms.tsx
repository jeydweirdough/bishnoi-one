"use client";

import { Check, Pencil, Plus, Star, Trash2, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/inventory/platform/ui/button";
import { Field, FormError, Input } from "@/src/modules/inventory/platform/ui/field";
import { deleteLocation, saveLocation, saveWarehouse } from "@/src/modules/inventory/actions/inventory";
import type { Warehouse } from "@/src/modules/inventory/lib/types";
import { useSave } from "@/src/modules/inventory/components/lines";

/** Adding a warehouse, or changing one's code, name and address. */
export function WarehouseForm({ warehouse, onDone }: { warehouse?: Pick<Warehouse, "id" | "code" | "name" | "address">; onDone?: () => void }) {
  const { pending, error, fields, save, shakeClass, anticipateClass } = useSave();
  const [d, setD] = useState({ code: warehouse?.code ?? "", name: warehouse?.name ?? "", address: warehouse?.address ?? "" });
  return (
    <form
      noValidate
      className={`grid gap-4 rounded-xl transition-all duration-300 sm:grid-cols-[8rem_minmax(0,1fr)_minmax(0,1.4fr)_auto] sm:items-end ${shakeClass} ${anticipateClass}`}
      onSubmit={(e) => {
        e.preventDefault();
        save(() => saveWarehouse(warehouse?.id ?? null, { code: d.code.trim(), name: d.name.trim(), address: d.address.trim() || null }), (out) => {
          onDone?.();
          return { message: warehouse ? "Warehouse saved" : `${d.name.trim()} added`, go: warehouse ? undefined : `/inventory/warehouses/${out.id}` };
        });
      }}
    >
      <Field label="Code" error={fields.code}>{(p) => <Input {...p} value={d.code} placeholder="MNL" onChange={(e) => setD({ ...d, code: e.target.value })} autoFocus />}</Field>
      <Field label="Name" error={fields.name}>{(p) => <Input {...p} value={d.name} placeholder="Manila Warehouse" onChange={(e) => setD({ ...d, name: e.target.value })} />}</Field>
      <Field label="Address" optional error={fields.address}>{(p) => <Input {...p} value={d.address} onChange={(e) => setD({ ...d, address: e.target.value })} />}</Field>
      <div className="flex gap-2">
        <Button type="submit" variant="primary" size="sm" loading={pending}>{warehouse ? "Save" : "Add warehouse"}</Button>
        {onDone && <Button size="sm" variant="quiet" onClick={onDone}>Cancel</Button>}
      </div>
      {error && <div className="sm:col-span-4"><FormError message={error} /></div>}
    </form>
  );
}

/** A button that opens the warehouse form in place. */
export function AddWarehouse({ startOpen = false }: { startOpen?: boolean }) {
  const [open, setOpen] = useState(startOpen);
  if (!open) return <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setOpen(true)}>Add warehouse</Button>;
  return (
    <div className="w-full rounded-xl border border-rule bg-sheet px-5 py-4 shadow-sheet">
      <WarehouseForm onDone={() => setOpen(false)} />
    </div>
  );
}

/** The edit icon beside a warehouse's name, opening its form below the header. */
export function EditWarehouse({ warehouse }: { warehouse: Pick<Warehouse, "id" | "code" | "name" | "address" | "isActive"> }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, start] = useTransition();
  return (
    <>
      <button suppressHydrationWarning type="button" title="Edit warehouse" onClick={() => setOpen(!open)} className="rounded-md p-1.5 text-ink-3 hover:bg-sheet hover:text-ink">
        <Pencil className="size-4" aria-hidden />
        <span className="sr-only">Edit warehouse</span>
      </button>
      {open && (
        <div className="fixed inset-x-0 top-0 z-40 flex justify-center p-4 lg:absolute lg:top-full lg:right-auto lg:left-0 lg:p-0 lg:pt-2">
          <div className="w-full max-w-3xl rounded-xl border border-rule bg-sheet px-5 py-4 shadow-overlay">
            <WarehouseForm warehouse={warehouse} onDone={() => setOpen(false)} />
            <div className="mt-3 border-t border-rule pt-3">
              <Button
                size="sm"
                variant="quiet"
                loading={pending}
                onClick={() =>
                  start(async () => {
                    const r = await saveWarehouse(warehouse.id, { isActive: !warehouse.isActive });
                    if (!r.ok) toast.error(r.error);
                    else {
                      toast.success(warehouse.isActive ? "Warehouse deactivated" : "Warehouse activated");
                      setOpen(false);
                      router.refresh();
                    }
                  })
                }
              >
                {warehouse.isActive ? "Deactivate warehouse" : "Activate warehouse"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

type Loc = Warehouse["locations"][number];

/** A warehouse's locations: zones, racks and bins. One is where stock goes by default. */
export function LocationsEditor({ warehouseId, locations, canManage }: { warehouseId: string; locations: Loc[]; canManage: boolean }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [shaking, setShaking] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [d, setD] = useState({ code: "", name: "" });
  const [error, setError] = useState<string | null>(null);

  function triggerShake() {
    setShaking(true);
    setTimeout(() => setShaking(false), 480);
  }

  function run(work: () => Promise<{ ok: boolean; error?: string; fields?: Record<string, string> }>, done: string) {
    start(async () => {
      try {
        const r = await work();
        if (!r.ok) {
          const err = Object.values(r.fields ?? {})[0] ?? r.error ?? "Something went wrong.";
          triggerShake();
          toast.error(err);
          return setError(err);
        }
        toast.success(done);
        setEditing(null);
        setError(null);
        router.refresh();
      } catch (err) {
        const errText = err instanceof Error ? err.message : "Connection failed. Please try again.";
        triggerShake();
        toast.error(errText);
        setError(errText);
      }
    });
  }

  const form = (key: string) => (
    <div className="flex flex-wrap items-center gap-2 bg-bench/50 px-5 py-2.5">
      <Input aria-label="Code" placeholder="A1" value={d.code} onChange={(e) => setD({ ...d, code: e.target.value })} className="!w-24" autoFocus />
      <Input aria-label="Name" placeholder="Aisle A, rack 1" value={d.name} onChange={(e) => setD({ ...d, name: e.target.value })} className="!w-64" />
      <Button size="sm" variant="primary" loading={pending} icon={<Check className="size-4" aria-hidden />} onClick={() => run(() => saveLocation(warehouseId, key === "new" ? null : key, { code: d.code.trim(), name: d.name.trim() }), "Location saved")}>
        Save
      </Button>
      <Button size="sm" variant="quiet" icon={<X className="size-4" aria-hidden />} onClick={() => setEditing(null)}>Cancel</Button>
    </div>
  );

  return (
    <div className={`rounded-xl transition-all duration-300 ${shaking ? "animate-shake ring-2 ring-danger/40 ring-offset-2" : ""} ${pending ? "animate-anticipate pointer-events-none opacity-90" : ""}`}>
      <ul className="divide-y divide-rule border-t border-rule">
        {locations.map((loc) =>
          editing === loc.id ? (
            <li key={loc.id}>{form(loc.id)}</li>
          ) : (
            <li key={loc.id} className="flex items-center justify-between gap-3 px-5 py-2.5">
              <span className="min-w-0 text-sm">
                <span className={`font-mono font-semibold ${loc.isActive ? "" : "text-ink-3 line-through"}`}>{loc.code}</span>
                <span className="text-ink-2"> · {loc.name}</span>
                {loc.isDefault && <span className="ml-2 text-meta font-semibold text-ink">Default</span>}
                <span className="block text-meta text-ink-3">{loc.units} units · {loc.products} products{!loc.isActive && " · switched off"}</span>
              </span>
              {canManage && (
                <span className="flex shrink-0 items-center gap-1">
                  {!loc.isDefault && loc.isActive && (
                    <button suppressHydrationWarning type="button" title={`Make ${loc.code} the default`} onClick={() => run(() => saveLocation(warehouseId, loc.id, { isDefault: true }), `${loc.code} set as default`)} className="rounded-md p-1.5 text-ink-3 hover:bg-bench hover:text-ink">
                      <Star className="size-4" aria-hidden />
                    </button>
                  )}
                  {!loc.isDefault && (
                    <Button size="sm" variant="quiet" onClick={() => run(() => saveLocation(warehouseId, loc.id, { isActive: !loc.isActive }), loc.isActive ? `${loc.code} deactivated` : `${loc.code} activated`)}>
                      {loc.isActive ? "Deactivate" : "Activate"}
                    </Button>
                  )}
                  <button suppressHydrationWarning type="button" title={`Rename ${loc.code}`} onClick={() => { setEditing(loc.id); setD({ code: loc.code, name: loc.name }); setError(null); }} className="rounded-md p-1.5 text-ink-3 hover:bg-bench hover:text-ink">
                    <Pencil className="size-4" aria-hidden />
                  </button>
                  {!loc.isDefault && loc.units === 0 && (
                    <button suppressHydrationWarning type="button" title={`Delete ${loc.code}`} onClick={() => run(() => deleteLocation(warehouseId, loc.id), `${loc.code} deleted`)} className="rounded-md p-1.5 text-ink-3 hover:bg-bench hover:text-danger">
                      <Trash2 className="size-4" aria-hidden />
                    </button>
                  )}
                </span>
              )}
            </li>
          ),
        )}
        {editing === "new" && <li>{form("new")}</li>}
      </ul>
      {canManage && editing !== "new" && (
        <div className="px-5 py-3">
          <Button size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => { setEditing("new"); setD({ code: "", name: "" }); setError(null); }}>
            Add location
          </Button>
        </div>
      )}
      {error && <div className="px-5 pb-3"><FormError message={error} /></div>}
    </div>
  );
}
