"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { SectionTitle } from "@/src/platform/ui/sheet";
import { createProduct, updateProduct, type ProductInput } from "../actions/inventory";
import { makeFormat } from "@/src/platform/lib/format";
import type { InventoryReference, Org, Product } from "@/src/platform/lib/types";

const CODE = /^[A-Za-z0-9][A-Za-z0-9._/-]*$/;

export function ProductForm({
  module,
  reference,
  product,
  canEdit = true,
  org,
}: {
  module: string;
  reference: InventoryReference;
  product?: Product;
  canEdit?: boolean;
  org: Org;
}) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  // Active price types, plus any switched-off one this product still has a price for.
  const types = reference.priceTypes.filter((t) => t.isActive || product?.prices[t.code] !== undefined);

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const text = (name: string) => String(data.get(name) ?? "").trim();
    const input: ProductInput = {
      code: text("code"),
      name: text("name"),
      genericName: text("genericName") || null,
      strength: text("strength") || null,
      form: text("form") || null,
      unit: text("unit"),
    };
    const problems: Record<string, string> = {};
    if (!CODE.test(input.code)) problems.code = "Use letters and numbers, with - . / or _ between them.";
    const prices: Record<string, number | null> = {};
    for (const t of types) {
      const raw = text(`price-${t.code}`);
      if (!raw) {
        prices[t.code] = null;
        continue;
      }
      const centavos = fmt.toCentavos(raw);
      if (centavos === null) problems[t.code] = "Enter an amount like 1,250.00.";
      else prices[t.code] = centavos;
    }
    if (Object.keys(problems).length) {
      setFields(problems);
      setError("Some fields need a look.");
      return;
    }

    start(async () => {
      if (product) {
        const result = await updateProduct(product.id, input, prices);
        if (!result.ok) {
          setError(result.error);
          setFields(result.fields ?? {});
          return;
        }
        setError(null);
        setFields({});
        toast.success(`${input.name} saved`);
        return;
      }
      const set = Object.fromEntries(Object.entries(prices).filter((entry): entry is [string, number] => entry[1] !== null));
      const result = await createProduct({ ...input, prices: set });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(`${input.name} added`);
      router.push(`/m/${module}/products/${result.data.id}`);
      router.refresh();
    });
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-6">
      <fieldset disabled={!canEdit} className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
        <Field label="Code" hint="Your SKU, e.g. AMOX-500" error={fields.code}>
          {(p) => <Input {...p} name="code" defaultValue={product?.code} maxLength={40} required className="uppercase" />}
        </Field>
        <Field label="Name" hint="As reps should see it on a quote" error={fields.name}>
          {(p) => <Input {...p} name="name" defaultValue={product?.name} maxLength={120} required />}
        </Field>
        <Field label="Generic name" optional error={fields.genericName}>
          {(p) => <Input {...p} name="genericName" defaultValue={product?.genericName ?? ""} maxLength={120} />}
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Strength" optional error={fields.strength}>
            {(p) => <Input {...p} name="strength" defaultValue={product?.strength ?? ""} maxLength={60} placeholder="500 mg" />}
          </Field>
          <Field label="Form" optional error={fields.form}>
            {(p) => <Input {...p} name="form" defaultValue={product?.form ?? ""} maxLength={60} placeholder="Capsule" />}
          </Field>
        </div>
        <Field label="Unit" hint="What one unit on a quote is" error={fields.unit}>
          {(p) => <Input {...p} name="unit" defaultValue={product?.unit} maxLength={60} required placeholder="Box of 100" />}
        </Field>
      </fieldset>

      <fieldset disabled={!canEdit} className="border-t border-rule pt-4">
        <SectionTitle icon="pricing">Prices per unit</SectionTitle>
        <p className="mb-3 text-meta text-ink-3">
          Leave a price empty if this product isn&apos;t sold at it. Each division only sees the prices its pricing rules allow.
        </p>
        <div className="grid gap-x-6 gap-y-4 sm:grid-cols-3">
          {types.map((t) => (
            <Field key={t.code} label={t.isActive ? t.name : `${t.name} (switched off)`} error={fields[t.code]}>
              {(p) => (
                <div className="flex items-center gap-1.5">
                  <span className="text-ink-3">{fmt.symbol}</span>
                  <Input
                    {...p}
                    name={`price-${t.code}`}
                    inputMode="decimal"
                    defaultValue={fmt.pesosText(product?.prices[t.code])}
                    placeholder="0.00"
                    className="text-right tabular-nums"
                  />
                </div>
              )}
            </Field>
          ))}
        </div>
      </fieldset>

      <FormError message={error} />
      {canEdit && (
        <Button type="submit" variant="primary" loading={pending}>
          {product ? "Save product" : "Add product"}
        </Button>
      )}
    </form>
  );
}
