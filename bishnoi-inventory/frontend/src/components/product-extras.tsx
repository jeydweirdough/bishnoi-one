"use client";

import { ImagePlus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { CellInput, FormError, Select } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { deleteImage, removeSupplierPrice, setSupplierPrice, uploadImage } from "../actions/inventory";
import type { Product, Ref } from "../lib/types";
import { QuickAdd } from "./quick-add";

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
        <figure key={id} className="group relative size-28 overflow-hidden rounded-[14px] border border-rule bg-bench">
          {/* eslint-disable-next-line @next/next/no-img-element -- served through our own route, sized by the box */}
          <img src={`/products/${productId}/images/${id}`} alt="" className="size-full object-contain" />
          {canEdit && (
            <button
              type="button"
              title="Remove this picture"
              onClick={() =>
                start(async () => {
                  const result = await deleteImage(productId, id);
                  if (!result.ok) toast.error(result.error);
                  else router.refresh();
                })
              }
              className="absolute top-1 right-1 rounded-full bg-sheet/90 p-1 text-ink-3 opacity-0 group-hover:opacity-100 hover:text-danger focus:opacity-100"
            >
              <Trash2 className="size-4" aria-hidden />
              <span className="sr-only">Remove this picture</span>
            </button>
          )}
        </figure>
      ))}
      {canEdit && images.length < 8 && (
        <>
          <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={(e) => e.target.files?.[0] && add(e.target.files[0])} />
          <Button className="!h-28 !w-28 flex-col" icon={<ImagePlus className="size-5" aria-hidden />} loading={pending} onClick={() => input.current?.click()}>
            Add picture
          </Button>
        </>
      )}
      {images.length === 0 && !canEdit && <p className="text-meta text-ink-3">No pictures.</p>}
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
        setError("Pick a supplier and give their price.");
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
        <p className="py-2 text-meta text-ink-3">No supplier prices yet. They&apos;re set here, or when a purchase order is placed.</p>
      ) : (
        <ul className="divide-y divide-rule">
          {product.supplierPrices.map((sp) => (
            <li key={sp.supplier.id} className="flex items-baseline justify-between gap-3 py-2 text-sm">
              <span className="min-w-0">
                <span className="font-semibold">{sp.supplier.name}</span>
                {sp.price === cheapest && product.supplierPrices.length > 1 && <span className="ml-2 text-meta text-ink">Lowest</span>}
                <span className="block text-meta text-ink-3">
                  {[sp.supplierSku && `Their code ${sp.supplierSku}`, sp.leadTimeDays != null && `${sp.leadTimeDays} days lead time`].filter(Boolean).join(" · ") || "—"}
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-2">
                <span className="tabular-nums">{fmt.peso(sp.price)}</span>
                {canEdit && (
                  <button
                    type="button"
                    title={`Remove ${sp.supplier.name}'s price`}
                    className="rounded-full p-1 text-ink-3 hover:bg-bench hover:text-danger"
                    onClick={() => start(async () => { const r = await removeSupplierPrice(product.id, sp.supplier.id); if (!r.ok) toast.error(r.error); else router.refresh(); })}
                  >
                    <Trash2 className="size-4" aria-hidden />
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-rule pt-3">
          <Select
            aria-label="Supplier"
            value={adding.supplierId}
            onChange={(e) => setAdding({ ...adding, supplierId: e.target.value })}
            className="min-w-40 flex-1"
          >
            <option value="">Supplier…</option>
            {suppliers.filter((s) => s.isActive && !listed.has(s.id)).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            {newSuppliers.filter((n) => !suppliers.some((s) => s.id === n.id)).map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
          </Select>
          {canAddSupplier && (
            <QuickAdd kind="supplier" label="New" onAdded={(a) => { setNewSuppliers((l) => [...l, { id: a.value, name: a.label }]); setAdding((x) => ({ ...x, supplierId: a.value })); }} />
          )}
          <CellInput aria-label="Their price" placeholder="Price" inputMode="decimal" value={adding.price} onChange={(e) => setAdding({ ...adding, price: e.target.value })} className="w-24" />
          <CellInput aria-label="Their code" placeholder="Their code" value={adding.sku} onChange={(e) => setAdding({ ...adding, sku: e.target.value })} className="w-28 !text-left" />
          <CellInput aria-label="Lead time in days" placeholder="Days" inputMode="numeric" value={adding.lead} onChange={(e) => setAdding({ ...adding, lead: e.target.value.replace(/\D/g, "") })} className="w-16" />
          <Button size="sm" loading={pending} onClick={add}>
            Add price
          </Button>
        </div>
      )}
      <div className="mt-2">
        <FormError message={error} />
      </div>
    </div>
  );
}
