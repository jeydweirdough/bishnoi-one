"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, useTransition, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { saveCatalogItem, saveLocation, saveProduct, saveSupplier, saveWarehouse } from "../actions/inventory";

// Adding what a form needs without leaving it. Beside a picker whose list
// lacks the thing (a new supplier, a unit nobody has used yet), a "+ New"
// opens a small form in a pop-up; saving it adds the thing and picks it, and
// whatever was typed in the form around it stays as it was.

export type QuickKind = "category" | "brand" | "unit" | "supplier" | "warehouse" | "location" | "product";
export type Added = {
  kind: QuickKind;
  value: string;
  label: string;
  /** A new product's particulars, for a line that picks it straight away. */
  product?: { sku: string; name: string; unit: string; costPrice: number; sellingPrice: number; trackBatches: boolean; trackExpiry: boolean; trackSerials: boolean };
};
/** Which things this person may add, as the screens work it out from their role. */
export type CanAdd = Partial<Record<QuickKind, boolean>>;

const WHAT: Record<QuickKind, string> = {
  category: "category",
  brand: "brand",
  unit: "unit of measure",
  supplier: "supplier",
  warehouse: "warehouse",
  location: "location",
  product: "product",
};

type Context = {
  org?: Org;
  categories?: { id: string; path: string }[];
  units?: { code: string; name: string }[];
  /** For a location: the warehouse it goes in. */
  warehouseId?: string;
};

type Outcome = { ok: true; data: { id?: string; code?: string } } | { ok: false; error: string; fields?: Record<string, string> };

/** The "+ New …" link, and the pop-up behind it. */
export function QuickAdd({ kind, onAdded, context = {}, label }: { kind: QuickKind; onAdded: (added: Added) => void; context?: Context; label?: string }) {
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [pending, start] = useTransition();
  const [v, setV] = useState<Record<string, string>>({});
  const [flags, setFlags] = useState({ batches: false, serials: false });
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const set = (k: string) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });
  const fmt = context.org ? makeFormat(context.org) : null;
  // The pop-up is drawn at the end of the page, outside the form it sits
  // beside: a form can't hold another form.
  const [showing, setShowing] = useState(false);
  useEffect(() => {
    if (showing && !dialog.current?.open) dialog.current?.showModal();
  }, [showing]);

  function open() {
    setV(kind === "unit" ? {} : kind === "product" ? { unitCode: context.units?.[0]?.code ?? "pc" } : {});
    setFlags({ batches: false, serials: false });
    setError(null);
    setFields({});
    setShowing(true);
  }

  function run(): Promise<Outcome> {
    const t = (k: string) => (v[k] ?? "").trim();
    switch (kind) {
      case "category":
        return saveCatalogItem("categories", null, { name: t("name"), parentId: t("parentId") || null }) as Promise<Outcome>;
      case "brand":
        return saveCatalogItem("brands", null, { name: t("name") }) as Promise<Outcome>;
      case "unit":
        return saveCatalogItem("units", null, { code: t("code").toLowerCase(), name: t("name") }) as Promise<Outcome>;
      case "supplier":
        return saveSupplier(null, {
          code: t("code"),
          name: t("name"),
          contactPerson: t("contactPerson") || null,
          phone: t("phone") || null,
          email: t("email") || null,
          paymentTerms: t("paymentTerms") || null,
        }) as Promise<Outcome>;
      case "warehouse":
        return saveWarehouse(null, { code: t("code"), name: t("name"), address: t("address") || null }) as Promise<Outcome>;
      case "location":
        return saveLocation(context.warehouseId ?? "", null, { code: t("code"), name: t("name") }) as Promise<Outcome>;
      case "product":
        return saveProduct(null, {
          sku: t("sku"),
          name: t("name"),
          unitCode: t("unitCode") || "pc",
          costPrice: fmt?.toCentavos(t("costPrice")) ?? 0,
          sellingPrice: fmt?.toCentavos(t("sellingPrice")) ?? 0,
          trackBatches: flags.batches,
          trackExpiry: flags.batches,
          trackSerials: flags.serials,
        }) as Promise<Outcome>;
    }
  }

  function save() {
    start(async () => {
      const result = await run();
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      const t = (k: string) => (v[k] ?? "").trim();
      const value = result.data.id ?? result.data.code ?? "";
      const shown =
        kind === "unit" ? `${t("name")} (${t("code").toLowerCase()})`
        : kind === "product" ? `${t("name")} · ${t("sku")}`
        : kind === "location" ? `${t("code").toUpperCase()} · ${t("name")}`
        : kind === "category" && t("parentId") ? `${context.categories?.find((c) => c.id === t("parentId"))?.path} › ${t("name")}`
        : t("name");
      const product =
        kind === "product"
          ? { sku: t("sku"), name: t("name"), unit: t("unitCode") || "pc", costPrice: fmt?.toCentavos(t("costPrice")) ?? 0, sellingPrice: fmt?.toCentavos(t("sellingPrice")) ?? 0, trackBatches: flags.batches, trackExpiry: flags.batches, trackSerials: flags.serials }
          : undefined;
      onAdded({ kind, value, label: shown, product });
      toast.success(`${t("name") || t("code")} added`, { description: "It's picked for you." });
      dialog.current?.close();
      // The lists everyone picks from now include it.
      router.refresh();
    });
  }

  const f = (name: string, title: string, props: Record<string, unknown> = {}, optional = false, hint?: string): ReactNode => (
    <Field label={title} optional={optional} error={fields[name]} hint={hint}>
      {(p) => <Input {...p} value={v[name] ?? ""} onChange={set(name)} {...props} />}
    </Field>
  );

  return (
    <>
      <button type="button" onClick={open} className="inline-flex items-center gap-0.5 text-meta font-semibold text-hema hover:underline">
        <Plus className="size-3.5" aria-hidden />
        {label ?? `New ${WHAT[kind]}`}
      </button>
      {showing && createPortal(
      <dialog
        ref={dialog}
        aria-labelledby={titleId}
        onClose={() => setShowing(false)}
        onCancel={(e) => pending && e.preventDefault()}
        className="m-auto w-[min(30rem,calc(100vw-2rem))] rounded-[3px] bg-sheet p-0 text-ink shadow-overlay"
      >
        {/* Its own form, so pressing Enter here saves this, not the form around it. */}
        <form
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            e.stopPropagation();
            save();
          }}
          className="space-y-4 p-5"
        >
          <h2 id={titleId} className="text-heading">
            New {WHAT[kind]}
          </h2>
          {kind === "category" && (
            <>
              {f("name", "Name", { autoFocus: true, placeholder: "Syringes" })}
              <Field label="Inside" optional>
                {(p) => (
                  <Select {...p} value={v.parentId ?? ""} onChange={set("parentId")}>
                    <option value="">At the top</option>
                    {context.categories?.map((c) => <option key={c.id} value={c.id}>{c.path}</option>)}
                  </Select>
                )}
              </Field>
            </>
          )}
          {kind === "brand" && f("name", "Name", { autoFocus: true })}
          {kind === "unit" && (
            <div className="grid grid-cols-[7rem_1fr] gap-4">
              {f("code", "Code", { autoFocus: true, placeholder: "box" })}
              {f("name", "Name", { placeholder: "Box" })}
            </div>
          )}
          {(kind === "supplier" || kind === "warehouse" || kind === "location") && (
            <div className="grid grid-cols-[7rem_1fr] gap-4">
              {f("code", "Code", { autoFocus: true, placeholder: kind === "supplier" ? "ABC" : kind === "warehouse" ? "MNL" : "A1" })}
              {f("name", "Name", { placeholder: kind === "supplier" ? "ABC Medical Supply" : kind === "warehouse" ? "Manila Warehouse" : "Aisle A, rack 1" })}
            </div>
          )}
          {kind === "supplier" && (
            <div className="grid gap-4 sm:grid-cols-2">
              {f("contactPerson", "Contact person", {}, true)}
              {f("phone", "Phone", { type: "tel" }, true)}
              {f("email", "Email", { type: "email" }, true)}
              {f("paymentTerms", "Payment terms", {}, true, "Net 30, COD…")}
            </div>
          )}
          {kind === "warehouse" && f("address", "Address", {}, true, "It starts with one location, Main area; add racks and bins on its page.")}
          {kind === "product" && (
            <>
              <div className="grid grid-cols-[9rem_1fr] gap-4">
                {f("sku", "SKU", { autoFocus: true })}
                {f("name", "Name")}
              </div>
              <div className="grid grid-cols-3 gap-4">
                <Field label="Unit" error={fields.unitCode}>
                  {(p) => (
                    <Select {...p} value={v.unitCode ?? "pc"} onChange={set("unitCode")}>
                      {context.units?.map((u) => <option key={u.code} value={u.code}>{u.name}</option>)}
                    </Select>
                  )}
                </Field>
                {f("costPrice", `Cost${fmt ? ` (${fmt.symbol})` : ""}`, { inputMode: "decimal" }, true)}
                {f("sellingPrice", `Selling${fmt ? ` (${fmt.symbol})` : ""}`, { inputMode: "decimal" }, true)}
              </div>
              <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
                <label className="flex items-center gap-2">
                  <input type="checkbox" className="size-4 accent-hema" checked={flags.batches} onChange={(e) => setFlags({ ...flags, batches: e.target.checked })} />
                  Batches and expiry dates
                </label>
                <label className="flex items-center gap-2">
                  <input type="checkbox" className="size-4 accent-hema" checked={flags.serials} onChange={(e) => setFlags({ ...flags, serials: e.target.checked })} />
                  Serial numbers
                </label>
              </div>
              <p className="text-meta text-ink-3">Reorder levels, brand, pictures and the rest can be filled in on the product&apos;s page later.</p>
            </>
          )}
          <FormError message={error} />
          <div className="flex justify-end gap-2">
            <Button onClick={() => dialog.current?.close()} disabled={pending}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={pending}>
              Add {WHAT[kind]}
            </Button>
          </div>
        </form>
      </dialog>,
        document.body,
      )}
    </>
  );
}

/**
 * A picker's label row with "+ New …" at its end, for a Field whose list may
 * lack what's needed. Shown only when `can` says the person may add one.
 */
export function WithAdd({ can, children, add }: { can: boolean | undefined; children: ReactNode; add: ReactNode }) {
  if (!can) return <>{children}</>;
  return (
    <div className="relative">
      <div className="absolute top-0 right-0 z-10">{add}</div>
      {children}
    </div>
  );
}

/** A list with what was just added on the end, until the page's own lists have it too. */
export function withAdded<T extends { value: string }>(options: T[], added: Added[], kind: QuickKind, make: (a: Added) => T): T[] {
  const have = new Set(options.map((o) => o.value));
  return [...options, ...added.filter((a) => a.kind === kind && !have.has(a.value)).map(make)];
}
