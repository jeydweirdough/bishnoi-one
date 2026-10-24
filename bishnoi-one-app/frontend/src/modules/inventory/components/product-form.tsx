"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";
import { Button, LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/src/modules/inventory/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import { makeFormat } from "@/src/modules/inventory/platform/lib/format";
import type { Org } from "@/src/modules/inventory/platform/lib/types";
import { saveProduct } from "@/src/modules/inventory/actions/inventory";
import { PRODUCT_STATUSES, PRODUCT_TYPES } from "@/src/modules/inventory/lib/labels";
import type { Product, ProductStatus, ProductType, Reference } from "@/src/modules/inventory/lib/types";
import { useSave } from "@/src/modules/inventory/components/lines";
import { QuickAdd, WithAdd, withAdded, type Added, type CanAdd } from "@/src/modules/inventory/components/quick-add";

type Draft = {
  sku: string;
  name: string;
  description: string;
  categoryId: string;
  brandId: string;
  productType: ProductType;
  unitCode: string;
  barcode: string;
  supplierId: string;
  costPrice: string;
  sellingPrice: string;
  taxRate: string;
  taxInclusive: boolean;
  minStock: string;
  maxStock: string;
  reorderPoint: string;
  reorderQty: string;
  status: ProductStatus;
  trackBatches: boolean;
  trackExpiry: boolean;
  trackSerials: boolean;
  parentId: string;
  variantLabel: string;
  attributes: [string, string][];
  cprNumber: string;
  cprValidUntil: string;
};

const whole = (s: string) => s.replace(/[^\d]/g, "");

/** Adding a product, or changing one: what it is, what it costs, when to reorder, and how it's tracked. */
export function ProductForm({ org, reference, product, parents, locked, preset, canAdd = {} }: {
  org: Org;
  /** What this person may add from here without leaving the form. */
  canAdd?: CanAdd;
  reference: Pick<Reference, "brands" | "categories" | "suppliers" | "units">;
  product?: Product;
  /** Products a new one could be a variant of. */
  parents: { id: string; name: string; sku: string }[];
  /** Stock has moved, so tracking and unit can't change. */
  locked: boolean;
  preset?: { parentId?: string };
}) {
  const fmt = makeFormat(org);
  const { pending, error, fields, save, shakeClass, anticipateClass } = useSave();
  const parent = product ? null : parents.find((p) => p.id === preset?.parentId);
  const [d, setD] = useState<Draft>(() => ({
    sku: product?.sku ?? (parent ? `${parent.sku}-` : ""),
    name: product?.name ?? (parent ? `${parent.name} ` : ""),
    description: product?.description ?? "",
    categoryId: product?.category?.id ?? "",
    brandId: product?.brand?.id ?? "",
    productType: product?.productType ?? "stock",
    unitCode: product?.unit ?? "pc",
    barcode: product?.barcode ?? "",
    supplierId: product?.supplier?.id ?? "",
    costPrice: product ? fmt.pesosText(product.costPrice) : "",
    sellingPrice: product ? fmt.pesosText(product.sellingPrice) : "",
    taxRate: product ? String(product.taxRateBp / 100) : "12",
    taxInclusive: product?.taxInclusive ?? true,
    minStock: String(product?.minStock ?? 0),
    maxStock: product?.maxStock == null ? "" : String(product.maxStock),
    reorderPoint: String(product?.reorderPoint ?? 0),
    reorderQty: String(product?.reorderQty ?? 0),
    status: product?.status ?? "active",
    trackBatches: product?.trackBatches ?? false,
    trackExpiry: product?.trackExpiry ?? false,
    trackSerials: product?.trackSerials ?? false,
    parentId: product?.parentId ?? preset?.parentId ?? "",
    variantLabel: product?.variantLabel ?? "",
    attributes: product ? Object.entries(product.attributes) : [["", ""]],
    cprNumber: product?.cpr.number ?? "",
    cprValidUntil: product?.cpr.validUntil ?? "",
  }));
  const set = (change: Partial<Draft>) => setD({ ...d, ...change });
  // Added from here ("+ New …"): picked at once, and listed until the page's own lists have them.
  const [added, setAdded] = useState<Added[]>([]);
  const took = (field: "categoryId" | "brandId" | "unitCode" | "supplierId") => (a: Added) => {
    setAdded((list) => [...list, a]);
    setD((current) => ({ ...current, [field]: a.value }));
  };
  const opt = (a: Added) => ({ value: a.value, label: a.label });

  function submit() {
    const input = {
      sku: d.sku.trim(),
      name: d.name.trim(),
      description: d.description.trim() || null,
      categoryId: d.categoryId || null,
      brandId: d.brandId || null,
      productType: d.productType,
      unitCode: d.unitCode,
      barcode: d.barcode.trim() || null,
      supplierId: d.supplierId || null,
      costPrice: fmt.toCentavos(d.costPrice) ?? 0,
      sellingPrice: fmt.toCentavos(d.sellingPrice) ?? 0,
      taxRateBp: Math.round((Number(d.taxRate) || 0) * 100),
      taxInclusive: d.taxInclusive,
      minStock: Number(d.minStock) || 0,
      maxStock: d.maxStock === "" ? null : Number(d.maxStock),
      reorderPoint: Number(d.reorderPoint) || 0,
      reorderQty: Number(d.reorderQty) || 0,
      status: d.status,
      trackBatches: d.trackBatches || d.trackExpiry,
      trackExpiry: d.trackExpiry,
      trackSerials: d.trackSerials,
      parentId: d.parentId || null,
      variantLabel: d.variantLabel.trim() || null,
      attributes: Object.fromEntries(d.attributes.filter(([k, v]) => k.trim() && v.trim()).map(([k, v]) => [k.trim(), v.trim()])),
      cprNumber: d.cprNumber.trim() || null,
      cprValidUntil: d.cprValidUntil || null,
    };
    save(() => saveProduct(product?.id ?? null, input), (out) => ({
      message: product ? "Product saved" : `${input.name} added`,
      go: `/inventory/products/${product?.id ?? out.id}`,
    }));
  }

  const categories = withAdded(reference.categories.filter((c) => c.isActive || c.id === d.categoryId).map((c) => ({ value: c.id, label: c.path })), added, "category", opt);
  const brands = withAdded(reference.brands.filter((b) => b.isActive || b.id === d.brandId).map((b) => ({ value: b.id, label: b.name })), added, "brand", opt);
  const units = withAdded(reference.units.filter((u) => u.isActive || u.code === d.unitCode).map((u) => ({ value: u.code, label: `${u.name} (${u.code})` })), added, "unit", opt);
  const suppliers = withAdded(reference.suppliers.filter((x) => x.isActive || x.id === d.supplierId).map((x) => ({ value: x.id, label: x.name })), added, "supplier", opt);
  const pickFrom = (list: { value: string; label: string }[]) => list.map((o) => <option key={o.value} value={o.value}>{o.label}</option>);
  const tracking = [
    { key: "trackBatches" as const, label: "Batch numbers", hint: "Each delivery's batch is tracked separately." },
    { key: "trackExpiry" as const, label: "Expiry dates", hint: "Per batch. Stock is issued first-expired, first-out." },
    { key: "trackSerials" as const, label: "Serial numbers", hint: "One per unit, for equipment." },
  ];

  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); submit(); }} className={`space-y-5 rounded-xl transition-all duration-300 ${shakeClass} ${anticipateClass}`}>
      <Sheet className="px-5 pt-4 pb-5 sm:px-6">
        <SectionTitle icon="products">Basic information</SectionTitle>
        <div className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="SKU" error={fields.sku}>
            {(p) => <Input {...p} value={d.sku} onChange={(e) => set({ sku: e.target.value })} autoFocus={!product} />}
          </Field>
          <Field label="Product name" error={fields.name} className="lg:col-span-2">
            {(p) => <Input {...p} value={d.name} onChange={(e) => set({ name: e.target.value })} />}
          </Field>
          <WithAdd can={canAdd.category} add={<QuickAdd kind="category" onAdded={took("categoryId")} context={{ categories: reference.categories.map((c) => ({ id: c.id, path: c.path })) }} label="New" />}>
            <Field label="Category" optional error={fields.categoryId}>
              {(p) => (
                <Select {...p} value={d.categoryId} onChange={(e) => set({ categoryId: e.target.value })}>
                  <option value="">None</option>
                  {pickFrom(categories)}
                </Select>
              )}
            </Field>
          </WithAdd>
          <WithAdd can={canAdd.brand} add={<QuickAdd kind="brand" onAdded={took("brandId")} label="New" />}>
            <Field label="Brand" optional error={fields.brandId}>
              {(p) => (
                <Select {...p} value={d.brandId} onChange={(e) => set({ brandId: e.target.value })}>
                  <option value="">None</option>
                  {pickFrom(brands)}
                </Select>
              )}
            </Field>
          </WithAdd>
          <Field label="Barcode" optional error={fields.barcode}>
            {(p) => <Input {...p} value={d.barcode} onChange={(e) => set({ barcode: e.target.value })} inputMode="numeric" />}
          </Field>
          <Field label="Product type" error={fields.productType} hint={locked ? "Locked after the first stock movement." : undefined}>
            {(p) => (
              <Select {...p} value={d.productType} disabled={locked} onChange={(e) => set({ productType: e.target.value as ProductType })}>
                {Object.entries(PRODUCT_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </Select>
            )}
          </Field>
          <WithAdd can={canAdd.unit && !locked} add={<QuickAdd kind="unit" onAdded={took("unitCode")} label="New" />}>
            <Field label="Unit of measure" error={fields.unitCode}>
              {(p) => (
                <Select {...p} value={d.unitCode} disabled={locked} onChange={(e) => set({ unitCode: e.target.value })}>
                  {pickFrom(units)}
                </Select>
              )}
            </Field>
          </WithAdd>
          <Field label="Status" error={fields.status}>
            {(p) => (
              <Select {...p} value={d.status} onChange={(e) => set({ status: e.target.value as ProductStatus })}>
                {Object.entries(PRODUCT_STATUSES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </Select>
            )}
          </Field>
          <Field label="Description" optional error={fields.description} className="sm:col-span-2 lg:col-span-3">
            {(p) => <Textarea {...p} rows={2} value={d.description} onChange={(e) => set({ description: e.target.value })} />}
          </Field>
        </div>
      </Sheet>

      <Sheet className="px-5 pt-4 pb-5 sm:px-6">
        <SectionTitle icon="letters">Product registration</SectionTitle>
        <p className="mt-1 text-meta text-ink-3">The FDA Certificate of Product Registration (CPR). Every active stock product needs one to be sold.</p>
        <div className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="CPR number" optional error={fields.cprNumber} hint="As printed on the certificate, for example DR-XY12345.">
            {(p) => <Input {...p} value={d.cprNumber} placeholder="DR-XY12345" onChange={(e) => set({ cprNumber: e.target.value.toUpperCase() })} />}
          </Field>
          <Field label="Valid until" optional error={fields.cprValidUntil}>
            {(p) => <Input {...p} type="date" value={d.cprValidUntil} onChange={(e) => set({ cprValidUntil: e.target.value })} />}
          </Field>
        </div>
      </Sheet>

      <Sheet className="px-5 pt-4 pb-5 sm:px-6">
        <SectionTitle icon="pricing">Purchasing and sales</SectionTitle>
        <div className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-2">
            <WithAdd can={canAdd.supplier} add={<QuickAdd kind="supplier" onAdded={took("supplierId")} label="New" />}>
              <Field label="Preferred supplier" optional error={fields.supplierId}>
                {(p) => (
                  <Select {...p} value={d.supplierId} onChange={(e) => set({ supplierId: e.target.value })}>
                    <option value="">None</option>
                    {pickFrom(suppliers)}
                  </Select>
                )}
              </Field>
            </WithAdd>
          </div>
          <Field label={`Cost price (${fmt.symbol})`} error={fields.costPrice} hint="Per unit. Used to value stock.">
            {(p) => <Input {...p} inputMode="decimal" value={d.costPrice} onChange={(e) => set({ costPrice: e.target.value })} />}
          </Field>
          <Field label={`Selling price (${fmt.symbol})`} error={fields.sellingPrice}>
            {(p) => <Input {...p} inputMode="decimal" value={d.sellingPrice} onChange={(e) => set({ sellingPrice: e.target.value })} />}
          </Field>
          <Field label="Tax rate (%)" error={fields.taxRateBp}>
            {(p) => <Input {...p} inputMode="decimal" value={d.taxRate} onChange={(e) => set({ taxRate: e.target.value.replace(/[^\d.]/g, "") })} />}
          </Field>
          <label className="flex items-center gap-2 self-end pb-2 text-sm text-ink-2 sm:col-span-3">
            <input suppressHydrationWarning type="checkbox" checked={d.taxInclusive} onChange={(e) => set({ taxInclusive: e.target.checked })} className="size-4 accent-hema" />
            Prices include tax
          </label>
        </div>
      </Sheet>

      <Sheet className="px-5 pt-4 pb-5 sm:px-6">
        <SectionTitle icon="stock">Stock levels</SectionTitle>
        <p className="mt-1 text-meta text-ink-3">Applied to available stock across all warehouses, excluding reserved stock.</p>
        <div className="mt-4 grid gap-5 sm:grid-cols-4">
          <Field label="Minimum stock" error={fields.minStock}>
            {(p) => <Input {...p} inputMode="numeric" value={d.minStock} onChange={(e) => set({ minStock: whole(e.target.value) })} />}
          </Field>
          <Field label="Reorder level" error={fields.reorderPoint} hint="Stock at or below this level is flagged as low.">
            {(p) => <Input {...p} inputMode="numeric" value={d.reorderPoint} onChange={(e) => set({ reorderPoint: whole(e.target.value) })} />}
          </Field>
          <Field label="Reorder quantity" error={fields.reorderQty}>
            {(p) => <Input {...p} inputMode="numeric" value={d.reorderQty} onChange={(e) => set({ reorderQty: whole(e.target.value) })} />}
          </Field>
          <Field label="Maximum stock" optional error={fields.maxStock}>
            {(p) => <Input {...p} inputMode="numeric" value={d.maxStock} onChange={(e) => set({ maxStock: whole(e.target.value) })} />}
          </Field>
        </div>
        <fieldset className="mt-5" disabled={locked}>
          <legend className="mb-2 text-meta font-medium text-ink-2">
            Tracking{locked && <span className="font-normal text-ink-3"> · locked after the first stock movement</span>}
          </legend>
          <div className="grid gap-3 sm:grid-cols-3">
            {tracking.map((t) => (
              <label key={t.key} className="flex gap-2 text-sm">
                <input suppressHydrationWarning
                  type="checkbox"
                  className="mt-0.5 size-4 accent-hema"
                  checked={d[t.key] || (t.key === "trackBatches" && d.trackExpiry)}
                  onChange={(e) => set({ [t.key]: e.target.checked })}
                />
                <span>
                  <span className="block text-ink">{t.label}</span>
                  <span className="block text-meta text-ink-3">{t.hint}</span>
                </span>
              </label>
            ))}
          </div>
          {fields.trackExpiry && <p className="mt-1 text-meta text-danger">{fields.trackExpiry}</p>}
        </fieldset>
      </Sheet>

      <Sheet className="px-5 pt-4 pb-5 sm:px-6">
        <SectionTitle icon="lists">Variant and specifications</SectionTitle>
        <div className="mt-4 grid gap-5 sm:grid-cols-2">
          <Field label="Parent product" optional error={fields.parentId} hint="For example, 3 mL is a variant of BD Syringe.">
            {(p) => (
              <Select {...p} value={d.parentId} onChange={(e) => set({ parentId: e.target.value })}>
                <option value="">None</option>
                {parents.filter((x) => x.id !== product?.id).map((x) => <option key={x.id} value={x.id}>{x.name} · {x.sku}</option>)}
              </Select>
            )}
          </Field>
          <Field label="Variant label" optional error={fields.variantLabel}>
            {(p) => <Input {...p} value={d.variantLabel} placeholder="3 mL" disabled={!d.parentId} onChange={(e) => set({ variantLabel: e.target.value })} />}
          </Field>
        </div>
        <p className="mt-5 mb-2 text-meta font-medium text-ink-2">Specifications</p>
        <div className="space-y-2">
          {d.attributes.map(([k, v], i) => (
            <div key={i} className="flex items-end gap-3">
              <Input aria-label={`Specification ${i + 1} name`} placeholder="Size" value={k} className="max-w-48" onChange={(e) => set({ attributes: d.attributes.map((a, j) => (j === i ? [e.target.value, a[1]] : a)) })} />
              <Input aria-label={`Specification ${i + 1} value`} placeholder="Medium" value={v} onChange={(e) => set({ attributes: d.attributes.map((a, j) => (j === i ? [a[0], e.target.value] : a)) })} />
              <button suppressHydrationWarning type="button" title="Remove specification" onClick={() => set({ attributes: d.attributes.filter((_, j) => j !== i) })} className="rounded-md p-1.5 text-ink-3 hover:bg-bench hover:text-danger">
                <X className="size-4" aria-hidden />
              </button>
            </div>
          ))}
        </div>
        {fields.attributes && <p className="mt-1 text-meta text-danger">{fields.attributes}</p>}
        <Button size="sm" variant="quiet" className="mt-2" icon={<Plus className="size-4" aria-hidden />} onClick={() => set({ attributes: [...d.attributes, ["", ""]] })}>
          Add specification
        </Button>
      </Sheet>

      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {product ? "Save changes" : "Add product"}
        </Button>
        <LinkButton href={product ? `/inventory/products/${product.id}` : "/inventory/products"} variant="quiet">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}
