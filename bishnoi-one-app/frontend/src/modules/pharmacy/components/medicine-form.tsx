"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/modules/pharmacy/platform/ui/button";
import { Choice, Field, FormError, FormGrid, Input, Select, Textarea } from "@/src/modules/pharmacy/platform/ui/field";
import { makeFormat } from "@/src/modules/pharmacy/platform/lib/format";
import type { Org } from "@/src/modules/pharmacy/platform/lib/types";
import { createMedicine, updateMedicine, type MedicineInput } from "@/src/modules/pharmacy/actions/pharmacy";
import { DOSAGE_FORMS, MEDICINE_STATUSES, MEDICINE_STATUS_HINTS, RX_CLASSES, RX_CLASS_HINTS } from "@/src/modules/pharmacy/lib/words";
import type { Medicine, MedicineReference, MedicineStatus, RxClass } from "@/src/modules/pharmacy/lib/types";

/** Adding a medicine to the catalogue, or changing one. */
export function MedicineForm({ medicine, reference, org, canEdit }: { medicine?: Medicine; reference: MedicineReference; org: Org; canEdit: boolean }) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const [pending, start] = useTransition();
  const [v, setV] = useState({
    code: medicine?.code ?? "",
    genericName: medicine?.genericName ?? "",
    brandId: medicine?.brand?.id ?? "",
    categoryId: medicine?.category?.id ?? "",
    strength: medicine?.strength ?? "",
    dosageForm: medicine?.dosageForm ?? "tablet",
    unit: medicine?.unit ?? "tablet",
    rxClass: (medicine?.rxClass ?? "rx") as RxClass,
    price: fmt.pesosText(medicine?.priceCentavos ?? null),
    reorderLevel: String(medicine?.reorderLevel ?? 0),
    status: (medicine?.status ?? "active") as MedicineStatus,
    notes: medicine?.notes ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const set = (change: Partial<typeof v>) => setV({ ...v, ...change });

  function submit() {
    const price = fmt.toCentavos(v.price || "0");
    if (price === null) {
      setFields({ priceCentavos: "Enter a price like 12.50." });
      return;
    }
    const input: MedicineInput = {
      code: v.code.trim(),
      genericName: v.genericName.trim(),
      brandId: v.brandId || null,
      categoryId: v.categoryId || null,
      strength: v.strength.trim() || null,
      dosageForm: v.dosageForm.trim(),
      unit: v.unit.trim(),
      rxClass: v.rxClass,
      priceCentavos: price,
      reorderLevel: Number.parseInt(v.reorderLevel, 10) || 0,
      status: v.status,
      notes: v.notes.trim() || null,
    };
    start(async () => {
      const result = medicine ? await updateMedicine(medicine.id, input) : await createMedicine(input);
      if (result.ok) {
        toast.success(medicine ? "Changes saved" : "Medicine added", { description: result.data.label });
        setError(null);
        setFields({});
        if (!medicine) router.push(`/pharmacy/medicines/${result.data.id}`);
        router.refresh();
        return;
      }
      setError(result.error);
      setFields(result.fields ?? {});
    });
  }

  const brands = reference.brands.filter((b) => b.isActive || b.id === medicine?.brand?.id);
  const categories = reference.categories.filter((c) => c.isActive || c.id === medicine?.category?.id);

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-6"
    >
      <fieldset disabled={!canEdit}>
        <FormGrid>
          <Field label="Generic name" size="lg" error={fields.genericName}>
            {(p) => <Input {...p} value={v.genericName} onChange={(e) => set({ genericName: e.target.value })} required autoFocus={!medicine} />}
          </Field>
          <Field label="Code" size="sm" error={fields.code} hint="Your own short code, unique in the catalogue.">
            {(p) => <Input {...p} value={v.code} onChange={(e) => set({ code: e.target.value.toUpperCase() })} required />}
          </Field>
          <Field label="Brand" size="md" optional error={fields.brandId}>
            {(p) => (
              <Select {...p} value={v.brandId} onChange={(e) => set({ brandId: e.target.value })}>
                <option value="">Unbranded / generic</option>
                {brands.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                    {b.manufacturer ? ` · ${b.manufacturer}` : ""}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Category" size="md" optional error={fields.categoryId}>
            {(p) => (
              <Select {...p} value={v.categoryId} onChange={(e) => set({ categoryId: e.target.value })}>
                <option value="">No category</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Strength" size="sm" optional error={fields.strength}>
            {(p) => <Input {...p} value={v.strength} onChange={(e) => set({ strength: e.target.value })} placeholder="500 mg" />}
          </Field>
          <Field label="Dosage form" size="sm" error={fields.dosageForm}>
            {(p) => (
              <>
                <Input {...p} list="dosage-forms" value={v.dosageForm} onChange={(e) => set({ dosageForm: e.target.value })} required />
                <datalist id="dosage-forms">
                  {DOSAGE_FORMS.map((f) => (
                    <option key={f} value={f} />
                  ))}
                </datalist>
              </>
            )}
          </Field>
          <Field label="Counted and sold by the" size="sm" error={fields.unit} hint="One unit: tablet, capsule, bottle, tube.">
            {(p) => <Input {...p} value={v.unit} onChange={(e) => set({ unit: e.target.value })} required />}
          </Field>
          <Field label={`Price per ${v.unit || "unit"} (${fmt.symbol})`} size="md" error={fields.priceCentavos}>
            {(p) => <Input {...p} inputMode="decimal" value={v.price} onChange={(e) => set({ price: e.target.value })} placeholder="0.00" />}
          </Field>
          <Field label="Reorder level" size="md" error={fields.reorderLevel} hint="At or below this many available, it shows as low stock.">
            {(p) => <Input {...p} inputMode="numeric" value={v.reorderLevel} onChange={(e) => set({ reorderLevel: e.target.value.replace(/\D/g, "") })} />}
          </Field>
          <div className="sm:col-span-6">
            <Choice
              name="rxClass"
              legend="How it's given out"
              value={v.rxClass}
              onChange={(rxClass) => set({ rxClass })}
              options={(Object.keys(RX_CLASSES) as RxClass[]).map((k) => ({ value: k, label: RX_CLASSES[k] }))}
            />
            <p className="mt-1 text-meta text-ink-3">{RX_CLASS_HINTS[v.rxClass]}</p>
          </div>
          <div className="sm:col-span-6">
            <Choice
              name="status"
              legend="Status"
              value={v.status}
              onChange={(status) => set({ status })}
              options={(Object.keys(MEDICINE_STATUSES) as MedicineStatus[]).map((k) => ({ value: k, label: MEDICINE_STATUSES[k] }))}
            />
            <p className="mt-1 text-meta text-ink-3">{MEDICINE_STATUS_HINTS[v.status]}</p>
          </div>
          <Field label="Notes" size="full" optional>
            {(p) => <Textarea {...p} value={v.notes} onChange={(e) => set({ notes: e.target.value })} maxLength={4000} />}
          </Field>
        </FormGrid>
      </fieldset>
      <FormError message={error} />
      {canEdit && (
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant="primary" loading={pending}>
            {medicine ? "Save changes" : "Add medicine"}
          </Button>
          <LinkButton href="/pharmacy/medicines" variant="quiet">
            {medicine ? "Back to medicines" : "Cancel"}
          </LinkButton>
        </div>
      )}
    </form>
  );
}
