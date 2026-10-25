"use client";

import { ImagePlus, Trash2, Upload, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/inventory/platform/ui/button";
import { CellInput, FormError, Select } from "@/src/modules/inventory/platform/ui/field";
import { makeFormat } from "@/src/modules/inventory/platform/lib/format";
import type { Org } from "@/src/modules/inventory/platform/lib/types";
import { deleteImage, removeSupplierPrice, setSupplierPrice, uploadImage } from "@/src/modules/inventory/actions/inventory";
import type { Product, Ref } from "@/src/modules/inventory/lib/types";
import { QuickAdd } from "@/src/modules/inventory/components/quick-add";

/**
 * A product's picture panel: the picture large; a small button in its corner
 * turns the box into a drop zone (drop an image, or click to browse), and the
 * thumbnails under it pick which one is shown, each removable.
 */
export function ProductGallery({ productId, name, images, canEdit }: { productId: string; name: string; images: string[]; canEdit: boolean }) {
  const router = useRouter();
  const [shown, setShown] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [over, setOver] = useState(false);
  const [pending, start] = useTransition();
  const current = shown && images.includes(shown) ? shown : (images[0] ?? null);
  const full = images.length >= 8;

  function add(file: File | undefined) {
    if (!file) return;
    if (!/^image\/(png|jpeg|webp)$/.test(file.type)) return void toast.error("Use a PNG, JPG or WebP image.");
    start(async () => {
      const form = new FormData();
      form.set("file", file);
      const result = await uploadImage(productId, form);
      if (!result.ok) return void toast.error(result.error);
      toast.success("Image added");
      setAdding(false);
      router.refresh();
    });
  }

  function remove(id: string) {
    start(async () => {
      const result = await deleteImage(productId, id);
      if (!result.ok) return void toast.error(result.error);
      if (shown === id) setShown(null);
      router.refresh();
    });
  }

  return (
    <div>
      <div className="relative aspect-square overflow-hidden rounded-xl bg-bench">
        {adding ? (
          <label
            onDragOver={(e) => {
              e.preventDefault();
              setOver(true);
            }}
            onDragLeave={() => setOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setOver(false);
              add(e.dataTransfer.files?.[0]);
            }}
            className={`flex size-full cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-[1.5px] border-dashed px-6 text-center transition-colors ${
              over ? "border-sage-deep bg-mint" : "border-rule-strong hover:border-ink-3"
            } ${pending ? "pointer-events-none opacity-60" : ""}`}
          >
            <span className="grid size-10 place-items-center rounded-lg border border-rule bg-sheet text-ink shadow-sm" aria-hidden>
              <Upload className="size-4.5" />
            </span>
            <span className="text-sm text-ink">
              {pending ? (
                "Uploading…"
              ) : (
                <>
                  Drop an image here or <span className="font-medium underline underline-offset-2">browse</span>
                </>
              )}
            </span>
            <span className="text-meta text-ink-3">PNG, JPG or WebP</span>
            <input suppressHydrationWarning type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" disabled={pending} onChange={(e) => add(e.target.files?.[0])} />
          </label>
        ) : current ? (
          // eslint-disable-next-line @next/next/no-img-element -- served through our own route, sized by the box
          <img src={`/inventory/products/${productId}/images/${current}`} alt={name} className="size-full object-contain" />
        ) : (
          <span className="flex size-full flex-col items-center justify-center gap-2 text-ink-3">
            <ImagePlus className="size-10" aria-hidden />
            <span className="text-meta">No image</span>
          </span>
        )}
        {canEdit && (adding || !full) && (
          <button suppressHydrationWarning
            type="button"
            onClick={() => setAdding(!adding)}
            disabled={pending}
            title={adding ? "Back to the image" : "Add an image"}
            aria-label={adding ? "Back to the image" : "Add an image"}
            className={`absolute grid size-9 place-items-center rounded-full border border-rule bg-sheet text-ink-2 shadow-sheet transition-colors hover:bg-mint hover:text-ink ${adding ? "top-2 right-2" : "right-2 bottom-2"}`}
          >
            {adding ? <X className="size-4" aria-hidden /> : <ImagePlus className="size-4" aria-hidden />}
          </button>
        )}
      </div>
      {images.length > 1 && (
        <ul className="mt-3 flex flex-wrap gap-2" aria-label="Images">
          {images.map((id) => (
            <li key={id} className="group relative">
              <button suppressHydrationWarning
                type="button"
                onClick={() => {
                  setShown(id);
                  setAdding(false);
                }}
                className={`block size-14 overflow-hidden rounded-lg border bg-bench ${id === current ? "border-ink ring-1 ring-ink" : "border-rule hover:border-ink-3"}`}
                aria-label="Show this image"
              >
                {/* eslint-disable-next-line @next/next/no-img-element -- served through our own route */}
                <img src={`/inventory/products/${productId}/images/${id}`} alt="" className="size-full object-contain" />
              </button>
              {canEdit && (
                <button suppressHydrationWarning
                  type="button"
                  onClick={() => remove(id)}
                  title="Remove image"
                  className="absolute -top-1.5 -right-1.5 grid size-5 place-items-center rounded-full border border-rule bg-sheet text-ink-3 opacity-0 group-hover:opacity-100 hover:text-danger focus:opacity-100"
                >
                  <X className="size-3" aria-hidden />
                  <span className="sr-only">Remove image</span>
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {images.length === 1 && canEdit && !adding && (
        <button suppressHydrationWarning type="button" onClick={() => remove(images[0])} className="mt-2 inline-flex items-center gap-1 text-meta text-ink-3 hover:text-danger">
          <Trash2 className="size-3.5" aria-hidden />
          Remove image
        </button>
      )}
    </div>
  );
}

/** A product's pictures: shown, added, removed. */
export function ProductImages({ productId, images, canEdit }: { productId: string; images: string[]; canEdit: boolean }) {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [pending, start] = useTransition();

  function add(file: File) {
    start(async () => {
      const form = new FormData();
      form.set("file", file);
      const result = await uploadImage(productId, form);
      if (!result.ok) toast.error(result.error);
      else router.refresh();
    });
  }

  return (
    <div className="flex flex-wrap gap-3">
      {images.map((id) => (
        <figure key={id} className="group relative size-28 overflow-hidden rounded-lg border border-rule bg-bench">
          {/* eslint-disable-next-line @next/next/no-img-element -- served through our own route, sized by the box */}
          <img src={`/inventory/products/${productId}/images/${id}`} alt="" className="size-full object-contain" />
          {canEdit && (
            <button suppressHydrationWarning
              type="button"
              title="Remove image"
              onClick={() =>
                start(async () => {
                  const result = await deleteImage(productId, id);
                  if (!result.ok) toast.error(result.error);
                  else router.refresh();
                })
              }
              className="absolute top-1 right-1 rounded-md bg-sheet/90 p-1 text-ink-3 opacity-0 group-hover:opacity-100 hover:text-danger focus:opacity-100"
            >
              <Trash2 className="size-4" aria-hidden />
              <span className="sr-only">Remove image</span>
            </button>
          )}
        </figure>
      ))}
      {canEdit && images.length < 8 && (
        <>
          <input suppressHydrationWarning ref={input} type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={(e) => e.target.files?.[0] && add(e.target.files[0])} />
          <Button className="!h-28 !w-28 flex-col" icon={<ImagePlus className="size-5" aria-hidden />} loading={pending} onClick={() => input.current?.click()}>
            Add image
          </Button>
        </>
      )}
      {images.length === 0 && !canEdit && <p className="text-meta text-ink-3">No images.</p>}
    </div>
  );
}

/** What each supplier charges for this product, editable in place. */
export function SupplierPrices({ org, product, suppliers, canEdit, canAddSupplier = false }: { org: Org; product: Product; suppliers: (Ref & { isActive: boolean })[]; canEdit: boolean; canAddSupplier?: boolean }) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState({ supplierId: "", price: "", sku: "", lead: "" });
  const listed = new Set(product.supplierPrices.map((p) => p.supplier.id));
  const [newSuppliers, setNewSuppliers] = useState<{ id: string; name: string }[]>([]);
  const cheapest = product.supplierPrices[0]?.price;

  function add() {
    start(async () => {
      const price = fmt.toCentavos(adding.price);
      if (!adding.supplierId || price === null) {
        setError("Select a supplier and enter the price.");
        return;
      }
      const result = await setSupplierPrice(product.id, adding.supplierId, { price, supplierSku: adding.sku || null, leadTimeDays: adding.lead ? Number(adding.lead) : null });
      if (!result.ok) return setError(result.error);
      setError(null);
      setAdding({ supplierId: "", price: "", sku: "", lead: "" });
      router.refresh();
    });
  }

  return (
    <div>
      {product.supplierPrices.length === 0 ? (
        <p className="py-2 text-meta text-ink-3">No supplier prices yet. Add one below, or one is recorded when a purchase order is placed.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[36rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-meta text-ink-3">
                <th scope="col" className="py-2 pr-3 font-medium">Supplier</th>
                <th scope="col" className="px-3 py-2 font-medium">Supplier code</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Lead time</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Price</th>
                {canEdit && <th scope="col" className="w-10 py-2"><span className="sr-only">Remove</span></th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {product.supplierPrices.map((sp) => (
                <tr key={sp.supplier.id}>
                  <th scope="row" className="py-2.5 pr-3 text-left font-semibold text-ink">
                    {sp.supplier.name}
                    {sp.price === cheapest && product.supplierPrices.length > 1 && <span className="ml-2 rounded-full bg-mint px-2 py-0.5 text-meta font-medium text-sage-deep">Lowest</span>}
                  </th>
                  <td className="px-3 py-2.5 text-ink-2">{sp.supplierSku ?? <span className="text-ink-3">—</span>}</td>
                  <td className="px-3 py-2.5 text-right text-ink-2 tabular-nums">{sp.leadTimeDays != null ? `${sp.leadTimeDays} ${sp.leadTimeDays === 1 ? "day" : "days"}` : <span className="text-ink-3">—</span>}</td>
                  <td className="px-3 py-2.5 text-right font-semibold text-ink tabular-nums">{fmt.peso(sp.price)}</td>
                  {canEdit && (
                    <td className="py-2.5 text-right">
                      <button suppressHydrationWarning
                        type="button"
                        title={`Remove ${sp.supplier.name}'s price`}
                        aria-label={`Remove ${sp.supplier.name}'s price`}
                        className="rounded-md p-1 text-ink-3 hover:bg-bench hover:text-danger"
                        onClick={() => start(async () => { const r = await removeSupplierPrice(product.id, sp.supplier.id); if (!r.ok) toast.error(r.error); else router.refresh(); })}
                      >
                        <Trash2 className="size-4" aria-hidden />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {canEdit && (
        <div className="mt-4 border-t border-rule pt-4">
          <p className="mb-2 text-sm font-semibold text-ink">Add a supplier price</p>
          <div className="grid gap-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end">
            <label className="block min-w-0">
              <span className="mb-1 block text-meta text-ink-3">Supplier</span>
              <span className="flex items-center gap-2">
                <Select aria-label="Supplier" value={adding.supplierId} onChange={(e) => setAdding({ ...adding, supplierId: e.target.value })} className="min-w-0 flex-1">
                  <option value="">Select a supplier</option>
                  {suppliers.filter((s) => s.isActive && !listed.has(s.id)).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  {newSuppliers.filter((n) => !suppliers.some((s) => s.id === n.id)).map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
                </Select>
                {canAddSupplier && (
                  <QuickAdd kind="supplier" label="New" onAdded={(a) => { setNewSuppliers((l) => [...l, { id: a.value, name: a.label }]); setAdding((x) => ({ ...x, supplierId: a.value })); }} />
                )}
              </span>
            </label>
            <label className="block min-w-0">
              <span className="mb-1 block text-meta text-ink-3">Supplier code</span>
              <CellInput aria-label="Supplier code" placeholder="Optional" value={adding.sku} onChange={(e) => setAdding({ ...adding, sku: e.target.value })} className="w-full !text-left" />
            </label>
            <label className="block min-w-0">
              <span className="mb-1 block text-meta text-ink-3">Lead time (days)</span>
              <CellInput aria-label="Lead time in days" placeholder="Optional" inputMode="numeric" value={adding.lead} onChange={(e) => setAdding({ ...adding, lead: e.target.value.replace(/\D/g, "") })} className="w-full" />
            </label>
            <label className="block min-w-0">
              <span className="mb-1 block text-meta text-ink-3">Price</span>
              <CellInput aria-label="Supplier price" placeholder="0.00" inputMode="decimal" value={adding.price} onChange={(e) => setAdding({ ...adding, price: e.target.value })} className="w-full" />
            </label>
            <Button variant="primary" loading={pending} onClick={add}>
              Add price
            </Button>
          </div>
        </div>
      )}
      <div className="mt-2">
        <FormError message={error} />
      </div>
    </div>
  );
}
