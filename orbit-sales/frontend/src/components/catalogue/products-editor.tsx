"use client";

import { Pencil, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { CatalogueProduct, Org, SalesRules } from "@/src/platform/lib/types";
import { deleteProduct, saveProduct, type ProductInput } from "../../actions/catalogue";

type PriceType = SalesRules["priceTypes"][number];
const TEXT = ["code", "name", "genericName", "strength", "form", "unit"] as const;
type Text = (typeof TEXT)[number];

/** The product list, with adding and changing one in a panel above it. */
export function ProductsEditor({
  products,
  priceTypes,
  org,
  mayCreate,
}: {
  products: CatalogueProduct[];
  priceTypes: PriceType[];
  org: Org;
  mayCreate: boolean;
}) {
  const fmt = makeFormat(org);
  const [editing, setEditing] = useState<CatalogueProduct | "new" | null>(null);
  // Only prices from the list are set here; a price typed on the quote has nothing to keep.
  const listed = priceTypes.filter((t) => t.entry === "list");

  return (
    <div className="space-y-5">
      {editing ? (
        <ProductForm key={editing === "new" ? "new" : editing.id} fmt={fmt} product={editing === "new" ? null : editing} listed={listed} onDone={() => setEditing(null)} />
      ) : (
        mayCreate && (
          <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing("new")}>
            Add product
          </Button>
        )
      )}

      <Sheet className="overflow-x-auto">
        {products.length === 0 ? (
          <Empty icon="products" title="No products here">
            {mayCreate ? "Add the products and services you quote, with their prices." : "Nothing matches."}
          </Empty>
        ) : (
          <table className="w-full min-w-[44rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                <th scope="col" className="px-5 py-2.5 font-semibold">Product</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">Unit</th>
                {listed.map((t) => (
                  <th key={t.code} scope="col" className="px-3 py-2.5 text-right font-semibold">
                    {t.name}
                  </th>
                ))}
                <th scope="col" className="px-5 py-2.5">
                  <span className="sr-only">Change</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {products.map((p) => (
                <tr key={p.id} className={p.isActive ? "" : "text-ink-3"}>
                  <td className="px-5 py-2.5">
                    <p className="font-medium">
                      {p.name}
                      {!p.isActive && <span className="ml-2 rounded-full bg-bench px-2 py-0.5 text-meta">Off</span>}
                    </p>
                    <p className="text-meta text-ink-3">{[p.code, p.genericName, p.strength, p.form].filter(Boolean).join(" · ")}</p>
                  </td>
                  <td className="px-3 py-2.5 text-ink-2">{p.unit}</td>
                  {listed.map((t) => (
                    <td key={t.code} className="px-3 py-2.5 text-right tabular-nums">
                      {p.prices[t.code] !== undefined ? fmt.peso(p.prices[t.code]) : <span className="text-danger">Not set</span>}
                    </td>
                  ))}
                  <td className="px-5 py-2.5 text-right">
                    {p.can.edit && (
                      <Button size="sm" variant="quiet" icon={<Pencil className="size-3.5" aria-hidden />} onClick={() => setEditing(p)} aria-label={`Change ${p.name}`}>
                        Change
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Sheet>
    </div>
  );
}

function ProductForm({ fmt, product, listed, onDone }: { fmt: Format; product: CatalogueProduct | null; listed: PriceType[]; onDone: () => void }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [values, setValues] = useState<Record<Text, string>>(() =>
    Object.fromEntries(TEXT.map((k) => [k, (product?.[k] as string | null) ?? (k === "unit" ? "box" : "")])) as Record<Text, string>,
  );
  const [prices, setPrices] = useState<Record<string, string>>(() =>
    Object.fromEntries(listed.map((t) => [t.code, fmt.pesosText(product?.prices[t.code] ?? null)])),
  );
  const [isActive, setActive] = useState(product?.isActive ?? true);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const set = (k: Text) => (e: { target: { value: string } }) => setValues({ ...values, [k]: e.target.value });

  function submit() {
    const problems: Record<string, string> = {};
    const amounts: Record<string, number | null> = {};
    for (const t of listed) {
      const text = prices[t.code].trim();
      const amount = text ? fmt.toCentavos(text) : null;
      if (text && !amount) problems[`price.${t.code}`] = "An amount like 1,250.00.";
      // Only what changed goes back: an untouched empty price stays empty.
      if (amount !== (product?.prices[t.code] ?? null)) amounts[t.code] = amount;
    }
    if (Object.keys(problems).length) {
      setFields(problems);
      setError("Some prices need a look.");
      return;
    }
    const input: ProductInput = {
      code: values.code.trim(),
      name: values.name.trim(),
      genericName: values.genericName.trim() || null,
      strength: values.strength.trim() || null,
      form: values.form.trim() || null,
      unit: values.unit.trim(),
      isActive,
      prices: amounts,
    };
    start(async () => {
      const result = await saveProduct(product?.id ?? null, input);
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(product ? "Product saved" : "Product added", { description: result.data.name });
      onDone();
      router.refresh();
    });
  }

  return (
    <Sheet className="px-5 pt-4 pb-5">
      <h2 className="mb-4 font-semibold">{product ? `Change ${product.name}` : "Add a product or service"}</h2>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="space-y-5"
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Code" error={fields.code} hint="Unique, e.g. AMX-500">
            {(p) => <Input {...p} value={values.code} onChange={set("code")} autoFocus={!product} />}
          </Field>
          <Field label="Name" error={fields.name} className="sm:col-span-2">
            {(p) => <Input {...p} value={values.name} onChange={set("name")} />}
          </Field>
          <Field label="Generic name" optional error={fields.genericName}>
            {(p) => <Input {...p} value={values.genericName} onChange={set("genericName")} />}
          </Field>
          <Field label="Strength" optional error={fields.strength}>
            {(p) => <Input {...p} value={values.strength} onChange={set("strength")} placeholder="500 mg" />}
          </Field>
          <Field label="Form" optional error={fields.form}>
            {(p) => <Input {...p} value={values.form} onChange={set("form")} placeholder="Tablet" />}
          </Field>
          <Field label="Sold by" error={fields.unit} hint="What one unit on a quote is">
            {(p) => <Input {...p} value={values.unit} onChange={set("unit")} placeholder="box of 100" />}
          </Field>
        </div>

        {listed.length > 0 && (
          <fieldset>
            <legend className="mb-2 text-sm font-semibold">Prices</legend>
            <div className="grid gap-4 sm:grid-cols-3">
              {listed.map((t) => (
                <Field key={t.code} label={`${t.name} (${fmt.symbol})`} optional error={fields[`price.${t.code}`] ?? fields.prices}>
                  {(p) => (
                    <Input {...p} inputMode="decimal" value={prices[t.code]} onChange={(e) => setPrices({ ...prices, [t.code]: e.target.value })} placeholder="0.00" />
                  )}
                </Field>
              ))}
            </div>
            <p className="mt-2 text-meta text-ink-3">A price left empty can&apos;t be quoted at that price type.</p>
          </fieldset>
        )}

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={isActive} onChange={(e) => setActive(e.target.checked)} className="size-4 accent-hema" />
          On sale: offered on new quotes
        </label>

        <FormError message={error} />
        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" variant="primary" loading={pending}>
            {product ? "Save changes" : "Add product"}
          </Button>
          <Button variant="quiet" onClick={onDone}>
            Cancel
          </Button>
          {product?.can.delete && (
            <span className="ml-auto">
              <ConfirmButton
                label="Delete"
                title={`Delete ${product.name}?`}
                body="Quotes already made keep it as it was. To stop offering it but keep it on record, switch it off instead."
                confirmLabel="Delete product"
                onConfirm={async () => {
                  const result = await deleteProduct(product.id);
                  if (!result.ok) {
                    toast.error(result.error);
                    return false;
                  }
                  toast.success(`${product.name} deleted`);
                  onDone();
                  router.refresh();
                }}
              />
            </span>
          )}
        </div>
      </form>
    </Sheet>
  );
}
