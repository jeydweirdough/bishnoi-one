"use client";

import { ExternalLink, Pencil, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, buttonClass } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, FormGrid, Input, Select } from "@/src/platform/ui/field";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { CatalogueProduct, FormFieldDef, FormLayout, Org, SalesRules, StockLevel } from "@/src/platform/lib/types";
import { ChoiceSelect, LayoutForm, extraChanges, toDraft, type ExtraDraft } from "@/src/modules/crm/components/extra/extra-fields";
import { extraText } from "@/src/modules/crm/components/extra/extra-values";
import { deleteProduct, proposePrices, saveProduct, type ProductInput } from "@/src/modules/crm/actions/catalogue";
import { Modal } from "antd";
import { StockBadge, StockWhere } from "@/src/modules/crm/components/catalogue/stock";

type PriceType = SalesRules["priceTypes"][number];
const TEXT = ["code", "name", "genericName", "strength", "form", "unit"] as const;
type Text = (typeof TEXT)[number];
// What Inventory keeps, for a product that comes from there: changed there, shown here.
const INVENTORYS = new Set(["code", "name", "unit", "isActive"]);
const SRP = "SRP";

/** The product list, with adding and changing one in a panel above it. */
export function ProductsEditor({
  products,
  priceTypes,
  org,
  mayCreate,
  layout,
  stock,
  inventoryUrl,
}: {
  products: CatalogueProduct[];
  priceTypes: PriceType[];
  org: Org;
  mayCreate: boolean;
  /** The product form as an admin laid it out (Settings → Forms). */
  layout: FormLayout;
  /** How much Inventory has, by code; null when the CRM isn't linked to Inventory. */
  stock: Record<string, StockLevel | null> | null;
  /** When the products come from Inventory: its screens, to add one there. */
  inventoryUrl: string | null;
}) {
  const fields = layout.sections.flatMap((s) => s.fields).filter((f) => !f.standard);
  const fmt = makeFormat(org);
  const [editing, setEditing] = useState<CatalogueProduct | "new" | null>(null);
  const [proposing, setProposing] = useState<CatalogueProduct | null>(null);
  // Only prices from the list are set here; a price typed on the quote has nothing to keep.
  const listed = priceTypes.filter((t) => t.entry === "list");

  return (
    <div className="space-y-5">
      {editing ? (
        <ProductForm
          key={editing === "new" ? "new" : editing.id}
          fmt={fmt}
          product={editing === "new" ? null : editing}
          listed={listed}
          layout={layout}
          onDone={() => setEditing(null)}
        />
      ) : mayCreate ? (
        <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing("new")}>
          Add product
        </Button>
      ) : (
        inventoryUrl && (
          <a href={`${inventoryUrl}/products`} target="_blank" rel="noreferrer" className={buttonClass("primary")}>
            <ExternalLink className="size-4" aria-hidden />
            Add it in Inventory
          </a>
        )
      )}

      <Sheet className="overflow-x-auto">
        {products.length === 0 ? (
          <Empty icon="products" title="No products here">
            {mayCreate
              ? "Add the products and services you quote, with their prices."
              : stock
                ? "Products are added in Inventory, and show up here within 15 minutes (or at once with Sync now)."
                : "Nothing matches."}
          </Empty>
        ) : (
          <table className="w-full min-w-[44rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                <th scope="col" className="px-5 py-2.5 font-semibold">Product</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">Unit</th>
                {stock && (
                  <th scope="col" className="px-3 py-2.5 font-semibold">
                    Stock
                  </th>
                )}
                {fields
                  .filter((f) => f.inList)
                  .map((f) => (
                    <th key={f.key} scope="col" className="px-3 py-2.5 font-semibold">
                      {f.label}
                    </th>
                  ))}
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
                      {!p.isActive && <span className="ml-2 rounded-md bg-bench px-2 py-0.5 text-meta">Off</span>}
                      {p.cpr?.state === "expired" && <span className="ml-2 rounded-md bg-danger/10 px-2 py-0.5 text-meta font-normal text-danger" title={`Valid until ${p.cpr.validUntil}: it shouldn't be sold until renewed`}>CPR expired</span>}
                      {p.cpr?.state === "expiring" && <span className="ml-2 rounded-md bg-[#fff4e0] px-2 py-0.5 text-meta font-normal text-[#8a5a00]" title={`Valid until ${p.cpr.validUntil}`}>CPR expiring</span>}
                    </p>
                    <p className="text-meta text-ink-3">{[p.code, p.genericName, p.strength, p.form, p.cpr ? `CPR ${p.cpr.number}` : null].filter(Boolean).join(" · ")}</p>
                  </td>
                  <td className="px-3 py-2.5 text-ink-2">{p.unit}</td>
                  {stock && (
                    <td className="px-3 py-2.5">
                      {p.fromInventory ? (
                        <>
                          <StockBadge level={stock[p.code]} />
                          <StockWhere level={stock[p.code]} />
                        </>
                      ) : (
                        <span className="text-meta text-ink-3">Kept here only</span>
                      )}
                    </td>
                  )}
                  {fields
                    .filter((f) => f.inList)
                    .map((f) => (
                      <td key={f.key} className="px-3 py-2.5 text-ink-2">
                        {extraText(fmt, f, p.extra[f.key]) ?? "—"}
                      </td>
                    ))}
                  {listed.map((t) => (
                    <td key={t.code} className="px-3 py-2.5 text-right tabular-nums">
                      {p.prices[t.code] !== undefined ? fmt.peso(p.prices[t.code]) : <span className="text-danger">Not set</span>}
                      {p.priceApprovals?.[t.code]?.status === "pending" && (
                        <span className="block text-meta font-normal text-[#8a5a00]" title="Waiting for Finance's approval; salespeople don't see it yet">
                          For approval
                        </span>
                      )}
                      {p.priceApprovals?.[t.code]?.status === "rejected" && (
                        <span className="block text-meta font-normal text-danger" title={p.priceApprovals[t.code].rejectionReason ?? undefined}>
                          Rejected
                        </span>
                      )}
                    </td>
                  ))}
                  <td className="px-5 py-2.5 text-right">
                    {p.can.edit ? (
                      <Button size="sm" variant="quiet" icon={<Pencil className="size-3.5" aria-hidden />} onClick={() => setEditing(p)} aria-label={`Change ${p.name}`}>
                        Change
                      </Button>
                    ) : (
                      p.can.propose && (
                        <Button size="sm" variant="quiet" icon={<Pencil className="size-3.5" aria-hidden />} onClick={() => setProposing(p)} aria-label={`Set prices for ${p.name}`}>
                          Set prices
                        </Button>
                      )
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Sheet>
      {proposing && <ProposePrices fmt={fmt} product={proposing} types={listed.filter((t) => t.code !== "SRP")} onDone={() => setProposing(null)} />}
    </div>
  );
}

/** A manager's prices for one product: each goes to Finance, and salespeople see it once approved. The SRP is Finance's. */
function ProposePrices({ fmt, product, types, onDone }: { fmt: Format; product: CatalogueProduct; types: { code: string; name: string }[]; onDone: () => void }) {
  const shown = (code: string) => {
    const a = product.priceApprovals?.[code];
    return a?.status === "pending" ? (a.proposedAmount ?? null) : (product.prices[code] ?? null);
  };
  const [texts, setTexts] = useState<Record<string, string>>(() => Object.fromEntries(types.map((t) => [t.code, fmt.pesosText(shown(t.code))])));
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();

  function save() {
    const prices: Record<string, number | null> = {};
    const wrong: Record<string, string> = {};
    for (const t of types) {
      const text = texts[t.code].trim();
      const amount = text ? fmt.toCentavos(text) : null;
      if (text && !amount) wrong[t.code] = "Enter an amount above zero.";
      else if ((amount ?? null) !== shown(t.code)) prices[t.code] = amount;
    }
    setFields(wrong);
    if (Object.keys(wrong).length) return;
    if (!Object.keys(prices).length) return void toast("Nothing changed");
    start(async () => {
      const r = await proposePrices(product.id, prices);
      if (!r.ok) {
        setError(r.error);
        return;
      }
      toast.success("Sent to Finance for approval", { description: `${product.name}: salespeople see the new prices once Finance approves them.` });
      onDone();
    });
  }

  return (
    <Modal open title={`Prices for ${product.name}`} onCancel={() => !saving && onDone()} onOk={save} okText="Send for approval" cancelText="Cancel" confirmLoading={saving} width={480} destroyOnHidden>
      <p className="mb-4 text-meta text-ink-3">
        Each price goes to Finance for approval; until then, salespeople keep the approved one. The SRP is set by Finance.
        {product.prices.SRP !== undefined && ` SRP: ${fmt.peso(product.prices.SRP)}.`}
      </p>
      <FormGrid>
        {types.map((t) => {
          const a = product.priceApprovals?.[t.code];
          return (
            <Field
              key={t.code}
              label={t.name}
              size="sm"
              error={fields[t.code]}
              hint={a?.status === "pending" ? "For approval" : a?.status === "rejected" ? `Rejected${a.rejectionReason ? `: ${a.rejectionReason}` : ""}` : product.prices[t.code] === undefined ? "Not set" : undefined}
            >
              {(p) => <Input {...p} inputMode="decimal" value={texts[t.code]} onChange={(e) => setTexts({ ...texts, [t.code]: e.target.value })} placeholder="0.00" />}
            </Field>
          );
        })}
      </FormGrid>
      <FormError message={error} />
    </Modal>
  );
}

function ProductForm({
  fmt,
  product,
  listed,
  layout,
  onDone,
}: {
  fmt: Format;
  product: CatalogueProduct | null;
  listed: PriceType[];
  layout: FormLayout;
  onDone: () => void;
}) {
  const custom = layout.sections.flatMap((s) => s.fields);
  const router = useRouter();
  const [pending, start] = useTransition();
  const [values, setValues] = useState<Record<Text, string>>(() =>
    Object.fromEntries(TEXT.map((k) => [k, (product?.[k] as string | null) ?? ""])) as Record<Text, string>,
  );
  const [prices, setPrices] = useState<Record<string, string>>(() =>
    Object.fromEntries(listed.map((t) => [t.code, fmt.pesosText(product?.prices[t.code] ?? null)])),
  );
  const [isActive, setActive] = useState(product?.isActive ?? true);
  const [needsPrescription, setNeedsPrescription] = useState(product?.needsPrescription ?? false);
  const [vatCategory, setVatCategory] = useState<NonNullable<ProductInput["vatCategory"]>>(product?.vatCategory ?? "standard");
  const [extra, setExtra] = useState<ExtraDraft>(() => toDraft(custom, product?.extra));
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const set = (k: Text) => (e: { target: { value: string } }) => setValues({ ...values, [k]: e.target.value });
  const fromInventory = product?.fromInventory ?? false;
  const locked = (key: string) => fromInventory && INVENTORYS.has(key);

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
      vatCategory,
      needsPrescription,
      isActive,
      prices: amounts,
      extra: extraChanges(custom, extra, product?.extra),
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

  /** A built-in field, drawn with the label and hints the admin gave it. */
  function standard(f: FormFieldDef) {
    if (locked(f.key)) {
      const shown = f.key === "isActive" ? (isActive ? "On sale" : "Inactive") : values[f.key as Text];
      return (
        <Field label={f.label} hint="From Inventory: change it there.">
          {(p) => <Input {...p} value={shown} readOnly disabled />}
        </Field>
      );
    }
    if (f.key === "isActive") {
      return (
        <label className="flex h-full items-end gap-2 pb-2 text-sm">
          <input suppressHydrationWarning type="checkbox" checked={isActive} onChange={(e) => setActive(e.target.checked)} className="size-4 accent-hema" />
          {f.label}: offered on new quotes
        </label>
      );
    }
    if (f.key === "form" || f.key === "unit") {
      return <ChoiceSelect field={f} value={values[f.key]} onChange={(v) => setValues({ ...values, [f.key]: v })} error={fields[f.key]} />;
    }
    if (!(TEXT as readonly string[]).includes(f.key)) return null;
    const k = f.key as Text;
    return (
      <Field label={f.label} optional={!f.required} error={fields[k]} hint={f.helpText ?? (k === "code" ? "Unique, e.g. AMX-500" : undefined)}>
        {(p) => <Input {...p} value={values[k]} onChange={set(k)} placeholder={f.placeholder ?? undefined} autoFocus={k === "code" && !product} />}
      </Field>
    );
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
        <LayoutForm layout={layout} standard={standard} draft={extra} onChange={setExtra} errors={fields} />

        {/* Rx: an order of it needs the prescription (an order link asks for it), and a pharmacist checks it. */}
        <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-rule px-4 py-3 has-[:checked]:border-danger/40 has-[:checked]:bg-danger-tint/40">
          <input suppressHydrationWarning type="checkbox" checked={needsPrescription} onChange={(e) => setNeedsPrescription(e.target.checked)} className="mt-0.5 size-4 accent-[#141414]" />
          <span>
            <span className="block text-sm font-medium text-ink">Needs a prescription (Rx)</span>
            <span className="block text-meta text-ink-3">Customers ordering it through an order link attach the prescription, and a pharmacist checks it.</span>
          </span>
        </label>

        <Field label="VAT" error={fields.vatCategory} hint="How Finance taxes it on quotes and invoices. Exempt: e.g. medicines on the FDA's VAT-exempt lists.">
          {(p) => (
            <Select {...p} value={vatCategory} onChange={(e) => setVatCategory(e.target.value as typeof vatCategory)}>
              <option value="standard">VATable (12%)</option>
              <option value="zero_rated">Zero-rated (0%)</option>
              <option value="exempt">VAT-exempt</option>
            </Select>
          )}
        </Field>

        {listed.length > 0 && (
          <fieldset>
            <legend className="mb-2 text-sm font-semibold">Prices</legend>
            <div className="grid gap-4 sm:grid-cols-3">
              {listed.map((t) => (
                <Field
                  key={t.code}
                  label={`${t.name} (${fmt.symbol})`}
                  optional={!(fromInventory && t.code === SRP)}
                  hint={fromInventory && t.code === SRP ? "From Inventory. A team's own price goes in Price books." : undefined}
                  error={fields[`price.${t.code}`] ?? fields.prices}
                >
                  {(p) => (
                    <Input
                      {...p}
                      inputMode="decimal"
                      value={prices[t.code]}
                      onChange={(e) => setPrices({ ...prices, [t.code]: e.target.value })}
                      placeholder="0.00"
                      readOnly={fromInventory && t.code === SRP}
                      disabled={fromInventory && t.code === SRP}
                    />
                  )}
                </Field>
              ))}
            </div>
            <p className="mt-2 text-meta text-ink-3">A price left empty can&apos;t be quoted at that price type.</p>
          </fieldset>
        )}

        <FormError message={error} />
        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" variant="primary" loading={pending}>
            {product ? "Save changes" : "Add product"}
          </Button>
          <Button variant="quiet" onClick={onDone}>
            Cancel
          </Button>
          {product?.can.delete && !fromInventory && (
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
