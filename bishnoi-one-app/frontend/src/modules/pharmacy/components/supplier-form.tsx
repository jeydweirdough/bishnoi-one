"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/modules/pharmacy/platform/ui/button";
import { Field, FormError, Input, Textarea } from "@/src/modules/pharmacy/platform/ui/field";
import { createSupplier, updateSupplier, type SupplierInput } from "@/src/modules/pharmacy/actions/pharmacy";
import type { Supplier } from "@/src/modules/pharmacy/lib/types";

export function SupplierForm({ supplier, canEdit = true }: { supplier?: Supplier; canEdit?: boolean }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [v, setV] = useState({
    name: supplier?.name ?? "",
    contactPerson: supplier?.contactPerson ?? "",
    phone: supplier?.phone ?? "",
    email: supplier?.email ?? "",
    address: supplier?.address ?? "",
    notes: supplier?.notes ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const set = (change: Partial<typeof v>) => setV({ ...v, ...change });

  function save(isActive = supplier?.isActive ?? true) {
    const input: SupplierInput = {
      name: v.name.trim(),
      contactPerson: v.contactPerson.trim() || null,
      phone: v.phone.trim() || null,
      email: v.email.trim() || null,
      address: v.address.trim() || null,
      notes: v.notes.trim() || null,
      isActive,
    };
    start(async () => {
      const result = supplier ? await updateSupplier(supplier.id, input) : await createSupplier(input);
      if (result.ok) {
        toast.success(supplier ? "Saved" : "Supplier added", { description: result.data.name });
        setError(null);
        setFields({});
        if (!supplier) router.push(`/pharmacy/suppliers/${result.data.id}`);
        router.refresh();
        return;
      }
      setError(result.error);
      setFields(result.fields ?? {});
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
      className="space-y-6"
    >
      <fieldset disabled={!canEdit} className="grid gap-5 sm:grid-cols-2">
        <Field label="Name" error={fields.name}>
          {(p) => <Input {...p} value={v.name} onChange={(e) => set({ name: e.target.value })} required autoFocus={!supplier} />}
        </Field>
        <Field label="Contact person" optional>
          {(p) => <Input {...p} value={v.contactPerson} onChange={(e) => set({ contactPerson: e.target.value })} />}
        </Field>
        <Field label="Phone" optional>
          {(p) => <Input {...p} type="tel" value={v.phone} onChange={(e) => set({ phone: e.target.value })} />}
        </Field>
        <Field label="Email" optional error={fields.email}>
          {(p) => <Input {...p} type="email" value={v.email} onChange={(e) => set({ email: e.target.value })} />}
        </Field>
        <Field label="Address" optional className="sm:col-span-2">
          {(p) => <Input {...p} value={v.address} onChange={(e) => set({ address: e.target.value })} />}
        </Field>
        <Field label="Notes" optional className="sm:col-span-2">
          {(p) => <Textarea {...p} value={v.notes} onChange={(e) => set({ notes: e.target.value })} maxLength={4000} />}
        </Field>
      </fieldset>
      <FormError message={error} />
      {canEdit && (
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant="primary" loading={pending}>
            {supplier ? "Save changes" : "Add supplier"}
          </Button>
          {supplier && (
            <Button onClick={() => save(!supplier.isActive)} disabled={pending}>
              {supplier.isActive ? "Switch supplier off" : "Switch supplier on"}
            </Button>
          )}
          <LinkButton href="/pharmacy/suppliers" variant="quiet">
            {supplier ? "Back to suppliers" : "Cancel"}
          </LinkButton>
        </div>
      )}
    </form>
  );
}
