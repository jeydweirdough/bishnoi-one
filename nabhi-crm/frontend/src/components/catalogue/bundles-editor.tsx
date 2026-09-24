"use client";

import { Pencil, Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { BundleRow, Org } from "@/src/platform/lib/types";
import { deleteBundle, saveBundle, type BundleInput } from "../../actions/catalogue";
import { StateTag } from "./catalogue-tabs";

type ProductRef = { id: string; name: string; code: string; unit: string; prices: Record<string, number> };

/** Bundles: products sold together at one set price. */
export function BundlesEditor({
  bundles,
  products,
  firstPrice,
  org,
  mayEdit,
}: {
  bundles: BundleRow[];
  products: ProductRef[];
  /** The price type a bundle's items are valued at, to show what the set saves. */
  firstPrice: { code: string; name: string } | null;
  org: Org;
  mayEdit: boolean;
}) {
  const fmt = makeFormat(org);
  const [editing, setEditing] = useState<BundleRow | "new" | null>(null);
  const product = (id: string) => products.find((p) => p.id === id);

  return (
    <div className="space-y-5">
      {editing ? (
        <BundleForm
          key={editing === "new" ? "new" : editing.id}
          fmt={fmt}
          bundle={editing === "new" ? null : editing}
          products={products}
          firstPrice={firstPrice}
          onDone={() => setEditing(null)}
        />
      ) : (
        mayEdit && (
          <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing("new")}>
            Add bundle
          </Button>
        )
      )}
      <Sheet>
        {bundles.length === 0 ? (
          <Empty icon="bundles" title="No bundles yet">
            A bundle is a set of products at one price. On a quote it&apos;s picked like a product.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {bundles.map((b) => (
              <li key={b.id} className="flex items-start justify-between gap-4 px-5 py-3">
                <div className="min-w-0">
                  <p className="font-medium">
                    {b.name} <span className="text-meta text-ink-3">{b.code}</span> <StateTag state={b.state} />
                  </p>
                  <p className="text-meta text-ink-2">
                    {b.items.map((i) => `${i.qty} × ${product(i.productId)?.name ?? "a product no longer here"}`).join(", ")}
                  </p>
                  <p className="text-meta text-ink-3">{b.asOneLine ? "One line on the quote" : "Shown as its items on the quote"}</p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <span className="font-semibold tabular-nums">{fmt.peso(b.priceCentavos)}</span>
                  {mayEdit && (
                    <Button size="sm" variant="quiet" icon={<Pencil className="size-3.5" aria-hidden />} onClick={() => setEditing(b)} aria-label={`Change ${b.name}`}>
                      Change
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </div>
  );
}

type Item = { productId: string; qty: string };

function BundleForm({
  fmt,
  bundle,
  products,
  firstPrice,
  onDone,
}: {
  fmt: Format;
  bundle: BundleRow | null;
  products: ProductRef[];
  firstPrice: { code: string; name: string } | null;
  onDone: () => void;
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [code, setCode] = useState(bundle?.code ?? "");
  const [name, setName] = useState(bundle?.name ?? "");
  const [price, setPrice] = useState(fmt.pesosText(bundle?.priceCentavos ?? null));
  const [asOneLine, setOneLine] = useState(bundle?.asOneLine ?? true);
  const [items, setItems] = useState<Item[]>(bundle?.items.map((i) => ({ productId: i.productId, qty: String(i.qty) })) ?? [{ productId: "", qty: "1" }]);
  const [startsOn, setStartsOn] = useState(bundle?.startsOn ?? "");
  const [endsOn, setEndsOn] = useState(bundle?.endsOn ?? "");
  const [isActive, setActive] = useState(bundle?.isActive ?? true);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const worth = firstPrice
    ? items.reduce((sum, i) => sum + (products.find((p) => p.id === i.productId)?.prices[firstPrice.code] ?? 0) * (Number(i.qty) || 0), 0)
    : 0;

  function submit() {
    const problems: Record<string, string> = {};
    const input: BundleInput = {
      code: code.trim(),
      name: name.trim(),
      priceCentavos: fmt.toCentavos(price) ?? 0,
      asOneLine,
      items: items.filter((i) => i.productId).map((i) => ({ productId: i.productId, qty: /^\d+$/.test(i.qty.trim()) ? Number(i.qty) : 0 })),
      startsOn: startsOn || null,
      endsOn: endsOn || null,
      isActive,
    };
    if (!input.code) problems.code = "Give it a code.";
    if (!input.name) problems.name = "Give it a name.";
    if (!input.priceCentavos) problems.priceCentavos = "An amount like 900.00.";
    if (input.items.length === 0 || input.items.some((i) => i.qty < 1)) problems.items = "Pick at least one product, each with a whole-number quantity.";
    if (Object.keys(problems).length) {
      setFields(problems);
      setError("Some fields need a look.");
      return;
    }
    start(async () => {
      const result = await saveBundle(bundle?.id ?? null, input);
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(bundle ? "Bundle saved" : "Bundle added", { description: result.data.name });
      onDone();
      router.refresh();
    });
  }

  return (
    <Sheet className="px-5 pt-4 pb-5">
      <h2 className="mb-4 font-semibold">{bundle ? `Change ${bundle.name}` : "Add a bundle"}</h2>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="space-y-5"
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Code" error={fields.code}>
            {(p) => <Input {...p} value={code} onChange={(e) => setCode(e.target.value)} autoFocus={!bundle} />}
          </Field>
          <Field label="Name" error={fields.name}>
            {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} />}
          </Field>
          <Field
            label={`Set price (${fmt.symbol})`}
            error={fields.priceCentavos}
            hint={worth > 0 && firstPrice ? `The items come to ${fmt.peso(worth)} at ${firstPrice.name}` : undefined}
          >
            {(p) => <Input {...p} inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="0.00" />}
          </Field>
        </div>

        <fieldset>
          <legend className="mb-2 text-sm font-semibold">What&apos;s in it</legend>
          <ul className="space-y-2">
            {items.map((item, i) => (
              <li key={i} className="flex items-center gap-2">
                <Select
                  aria-label={`Item ${i + 1}: product`}
                  value={item.productId}
                  onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, productId: e.target.value } : x)))}
                  className="min-w-0 flex-1"
                >
                  <option value="">Pick a product…</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} · {p.unit}
                    </option>
                  ))}
                </Select>
                <input
                  aria-label={`Item ${i + 1}: quantity`}
                  inputMode="numeric"
                  value={item.qty}
                  onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, qty: e.target.value } : x)))}
                  className="h-9 w-20 rounded-[3px] border border-control px-2 text-right"
                />
                {items.length > 1 && (
                  <Button size="sm" variant="quiet" onClick={() => setItems(items.filter((_, j) => j !== i))} aria-label={`Remove item ${i + 1}`}>
                    <X className="size-3.5" aria-hidden />
                  </Button>
                )}
              </li>
            ))}
          </ul>
          <Button size="sm" variant="quiet" className="mt-1 -ml-3" icon={<Plus className="size-3.5" aria-hidden />} onClick={() => setItems([...items, { productId: "", qty: "1" }])}>
            Add product
          </Button>
          {fields.items && <p className="mt-1 text-meta text-danger">{fields.items}</p>}
        </fieldset>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={asOneLine} onChange={(e) => setOneLine(e.target.checked)} className="size-4 accent-hema" />
          One line on the quote (untick to list its items, sharing the set price)
        </label>

        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Starts" optional error={fields.startsOn}>
            {(p) => <Input {...p} type="date" value={startsOn} onChange={(e) => setStartsOn(e.target.value)} />}
          </Field>
          <Field label="Ends" optional error={fields.endsOn}>
            {(p) => <Input {...p} type="date" value={endsOn} onChange={(e) => setEndsOn(e.target.value)} />}
          </Field>
          <label className="flex items-center gap-2 self-end pb-2 text-sm">
            <input type="checkbox" checked={isActive} onChange={(e) => setActive(e.target.checked)} className="size-4 accent-hema" />
            Switched on
          </label>
        </div>

        <FormError message={error} />
        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" variant="primary" loading={pending}>
            {bundle ? "Save changes" : "Add bundle"}
          </Button>
          <Button variant="quiet" onClick={onDone}>
            Cancel
          </Button>
          {bundle && (
            <span className="ml-auto">
              <ConfirmButton
                label="Delete"
                title={`Delete ${bundle.name}?`}
                body="Quotes already made keep it as it was."
                confirmLabel="Delete bundle"
                onConfirm={async () => {
                  const result = await deleteBundle(bundle.id);
                  if (!result.ok) {
                    toast.error(result.error);
                    return false;
                  }
                  toast.success(`${bundle.name} deleted`);
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
