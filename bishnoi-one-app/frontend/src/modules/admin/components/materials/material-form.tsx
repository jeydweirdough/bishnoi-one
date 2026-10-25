"use client";

import { Paperclip } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { saveMaterial, uploadDesign, type Material, type MaterialPage } from "@/src/modules/admin/actions/materials";
import { FormField, ModalFrame, inputClass } from "@/src/modules/admin/components/executive-modals";
import { Button } from "@/src/modules/admin/platform/ui/button";

const number = (v: string) => (v.trim() ? Number(v.replace(/,/g, "")) : null);

/**
 * Adds a promotional material with what it is, how many, and by when, and its
 * design attached; or changes those details while it's a draft or returned for
 * changes. A new design for an existing one is uploaded on its page, as a version.
 */
export function MaterialForm({ kinds, item, onClose, onSaved }: { kinds: string[]; item: Material | null; onClose: () => void; onSaved: (page: MaterialPage) => void }) {
  const [values, setValues] = useState({
    title: item?.title ?? "",
    kind: item?.kind ?? kinds[0] ?? "Leaflet",
    product: item?.product ?? "",
    quantity: item?.quantity ? String(item.quantity) : "",
    specs: item?.specs ?? "",
    neededBy: item?.neededBy ?? "",
    budget: item?.budget != null ? String(item.budget) : "",
    description: item?.description ?? "",
  });
  const [design, setDesign] = useState<File | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const set = (key: keyof typeof values) => (e: { target: { value: string } }) => setValues({ ...values, [key]: e.target.value });

  function save() {
    const wrong: Record<string, string> = {};
    if (values.title.trim().length < 2) wrong.title = "Give it a title.";
    const quantity = number(values.quantity);
    if (quantity !== null && (!Number.isInteger(quantity) || quantity < 1)) wrong.quantity = "A whole number, 1 or more.";
    const budget = number(values.budget);
    if (budget !== null && (Number.isNaN(budget) || budget < 0)) wrong.budget = "An amount in pesos.";
    if (design && design.size > 3 * 1024 * 1024) wrong.design = "The file is over 3 MB. Save a smaller PDF or picture.";
    if (Object.keys(wrong).length) return setErrors(wrong);
    start(async () => {
      const r = await saveMaterial(item?.id ?? null, {
        title: values.title.trim(),
        kind: values.kind,
        product: values.product.trim() || null,
        description: values.description.trim() || null,
        quantity,
        specs: values.specs.trim() || null,
        neededBy: values.neededBy || null,
        budget,
      });
      if (!r.ok) {
        setErrors(r.fields ?? {});
        setError(r.fields ? null : r.error);
        return;
      }
      let page = r.data;
      if (design) {
        const form = new FormData();
        form.set("file", design, design.name);
        const up = await uploadDesign(page.material.id, form);
        // The material is kept either way; a design that didn't go up can be added on its page.
        if (up.ok) page = up.data;
        else toast.error(`Material added, but the design wasn't: ${up.fields?.file ?? up.error}`);
      }
      toast.success(item ? "Material saved" : "Material added", { description: page.material.title });
      onSaved(page);
      onClose();
    });
  }

  return (
    <ModalFrame title={item ? "Change material" : "New promotional material"} subtitle={item ? item.title : "What it is, how many, and by when. Attach the design for the pharmacist's review."} onClose={onClose}>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
        className="space-y-5"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <FormField label="Title">
              <input suppressHydrationWarning value={values.title} onChange={set("title")} maxLength={160} placeholder="e.g. Glucare 500 mg leaflet" aria-invalid={errors.title ? true : undefined} className={inputClass} />
            </FormField>
            {errors.title && <p className="mt-1 text-meta text-danger">{errors.title}</p>}
          </div>
          <div>
            <FormField label="Type">
              <select suppressHydrationWarning value={values.kind} onChange={set("kind")} className={inputClass}>
                {kinds.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </FormField>
            {errors.kind && <p className="mt-1 text-meta text-danger">{errors.kind}</p>}
          </div>
          <div>
            <FormField label="Product" optional>
              <input suppressHydrationWarning value={values.product} onChange={set("product")} maxLength={160} placeholder="What it promotes" className={inputClass} />
            </FormField>
          </div>
          <div>
            <FormField label="Quantity needed" optional>
              <input suppressHydrationWarning value={values.quantity} onChange={set("quantity")} inputMode="numeric" placeholder="e.g. 500" aria-invalid={errors.quantity ? true : undefined} className={inputClass} />
            </FormField>
            {errors.quantity && <p className="mt-1 text-meta text-danger">{errors.quantity}</p>}
          </div>
          <div>
            <FormField label="Date needed" optional>
              <input suppressHydrationWarning type="date" value={values.neededBy} onChange={set("neededBy")} className={inputClass} />
            </FormField>
          </div>
          <div>
            <FormField label="Size and specifications" optional>
              <input suppressHydrationWarning value={values.specs} onChange={set("specs")} maxLength={300} placeholder="e.g. A5, 2 sides, glossy" className={inputClass} />
            </FormField>
          </div>
          <div>
            <FormField label="Budget" optional>
              <input suppressHydrationWarning value={values.budget} onChange={set("budget")} inputMode="decimal" placeholder="₱ for the whole run" aria-invalid={errors.budget ? true : undefined} className={inputClass} />
            </FormField>
            {errors.budget && <p className="mt-1 text-meta text-danger">{errors.budget}</p>}
          </div>
          <div className="sm:col-span-2">
            <FormField label="Description" optional>
              <textarea suppressHydrationWarning value={values.description} onChange={set("description")} maxLength={1000} rows={2} placeholder="Where it's used, what it says" className={inputClass} />
            </FormField>
          </div>
          {!item && (
            <div className="sm:col-span-2">
              <FormField label="Design" optional>
                <label className="flex cursor-pointer items-center gap-3 rounded-[14px] border border-dashed border-rule-strong px-3.5 py-3 text-sm text-ink-2 hover:border-ink">
                  <Paperclip className="size-4 shrink-0" aria-hidden />
                  <span className="min-w-0 flex-1 truncate">{design ? design.name : "Attach the design: a PDF or picture (PNG or JPG), up to 3 MB"}</span>
                  <input suppressHydrationWarning type="file" accept="application/pdf,image/png,image/jpeg" className="sr-only" onChange={(e) => setDesign(e.target.files?.[0] ?? null)} />
                </label>
              </FormField>
              {errors.design ? (
                <p className="mt-1 text-meta text-danger">{errors.design}</p>
              ) : (
                <p className="mt-1 text-meta text-ink-3">You can also add it later on the material&apos;s page, then submit it for review.</p>
              )}
            </div>
          )}
        </div>
        {error && (
          <p role="alert" className="rounded-[14px] bg-danger-tint px-3 py-2 text-meta text-danger">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2 border-t border-rule pt-4">
          <Button variant="quiet" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={pending}>
            {pending ? "Saving…" : item ? "Save changes" : "Add material"}
          </Button>
        </div>
      </form>
    </ModalFrame>
  );
}
