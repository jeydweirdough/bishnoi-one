"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Field, FormError, Input, Textarea } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { saveSupplier } from "../actions/inventory";
import type { Contact, Supplier } from "../lib/types";
import { useSave } from "./lines";

/** Adding a supplier, or changing one: who they are, how to reach them, and their terms. */
export function SupplierForm({ supplier }: { supplier?: Supplier }) {
  const { pending, error, fields, save } = useSave();
  const [d, setD] = useState({
    code: supplier?.code ?? "",
    name: supplier?.name ?? "",
    contactPerson: supplier?.contactPerson ?? "",
    email: supplier?.email ?? "",
    phone: supplier?.phone ?? "",
    address: supplier?.address ?? "",
    paymentTerms: supplier?.paymentTerms ?? "",
    leadTimeDays: supplier?.leadTimeDays == null ? "" : String(supplier.leadTimeDays),
    notes: supplier?.notes ?? "",
  });
  const [contacts, setContacts] = useState<Contact[]>(supplier?.contacts ?? []);
  const text = (k: keyof typeof d) => ({ value: d[k], onChange: (e: { target: { value: string } }) => setD({ ...d, [k]: e.target.value }) });

  function submit() {
    const input = {
      code: d.code.trim(),
      name: d.name.trim(),
      contactPerson: d.contactPerson.trim() || null,
      email: d.email.trim() || null,
      phone: d.phone.trim() || null,
      address: d.address.trim() || null,
      paymentTerms: d.paymentTerms.trim() || null,
      leadTimeDays: d.leadTimeDays === "" ? null : Number(d.leadTimeDays),
      notes: d.notes.trim() || null,
      contacts: contacts.filter((c) => c.name.trim()).map((c) => ({ name: c.name.trim(), role: c.role?.trim() || null, email: c.email?.trim() || null, phone: c.phone?.trim() || null })),
    };
    save(() => saveSupplier(supplier?.id ?? null, input), (out) => ({ message: supplier ? "Supplier saved" : `${input.name} added`, go: `/suppliers/${supplier?.id ?? out.id}` }));
  }

  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); submit(); }} className="space-y-5">
      <Sheet className="px-5 pt-4 pb-5 sm:px-6">
        <SectionTitle icon="suppliers">The supplier</SectionTitle>
        <div className="mt-4 grid gap-5 sm:grid-cols-3">
          <Field label="Code" error={fields.code}>{(p) => <Input {...p} {...text("code")} placeholder="ABC" autoFocus={!supplier} />}</Field>
          <Field label="Name" error={fields.name} className="sm:col-span-2">{(p) => <Input {...p} {...text("name")} placeholder="ABC Medical Supply" />}</Field>
          <Field label="Main contact" optional error={fields.contactPerson}>{(p) => <Input {...p} {...text("contactPerson")} />}</Field>
          <Field label="Email" optional error={fields.email}>{(p) => <Input {...p} type="email" {...text("email")} />}</Field>
          <Field label="Phone" optional error={fields.phone}>{(p) => <Input {...p} type="tel" {...text("phone")} />}</Field>
          <Field label="Address" optional error={fields.address} className="sm:col-span-3">{(p) => <Input {...p} {...text("address")} />}</Field>
          <Field label="Payment terms" optional error={fields.paymentTerms} hint="Net 30, COD…">{(p) => <Input {...p} {...text("paymentTerms")} />}</Field>
          <Field label="Lead time (days)" optional error={fields.leadTimeDays} hint="From order to delivery, as promised.">
            {(p) => <Input {...p} inputMode="numeric" value={d.leadTimeDays} onChange={(e) => setD({ ...d, leadTimeDays: e.target.value.replace(/\D/g, "") })} />}
          </Field>
          <Field label="Notes" optional error={fields.notes} className="sm:col-span-3">{(p) => <Textarea {...p} rows={2} {...text("notes")} />}</Field>
        </div>
      </Sheet>
      <Sheet className="px-5 pt-4 pb-5 sm:px-6">
        <SectionTitle icon="people">Other people to talk to</SectionTitle>
        <div className="mt-3 space-y-2">
          {contacts.map((c, i) => {
            const set = (change: Partial<Contact>) => setContacts(contacts.map((x, j) => (j === i ? { ...x, ...change } : x)));
            return (
              <div key={i} className="grid gap-2 sm:grid-cols-[1fr_1fr_1.2fr_1fr_auto] sm:items-center">
                <Input aria-label="Name" placeholder="Name" value={c.name} onChange={(e) => set({ name: e.target.value })} />
                <Input aria-label="Role" placeholder="Role" value={c.role ?? ""} onChange={(e) => set({ role: e.target.value })} />
                <Input aria-label="Email" placeholder="Email" value={c.email ?? ""} onChange={(e) => set({ email: e.target.value })} />
                <Input aria-label="Phone" placeholder="Phone" value={c.phone ?? ""} onChange={(e) => set({ phone: e.target.value })} />
                <button type="button" title="Remove" onClick={() => setContacts(contacts.filter((_, j) => j !== i))} className="justify-self-end rounded-[3px] p-1.5 text-ink-3 hover:bg-bench hover:text-danger">
                  <X className="size-4" aria-hidden />
                </button>
              </div>
            );
          })}
        </div>
        {Object.entries(fields).filter(([k]) => k.startsWith("contacts")).map(([k, v]) => <p key={k} className="mt-1 text-meta text-danger">{v}</p>)}
        <Button size="sm" variant="quiet" className="mt-2" icon={<Plus className="size-4" aria-hidden />} onClick={() => setContacts([...contacts, { name: "", role: null, email: null, phone: null }])}>
          Add a person
        </Button>
      </Sheet>
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>{supplier ? "Save changes" : "Add supplier"}</Button>
        <LinkButton href={supplier ? `/suppliers/${supplier.id}` : "/suppliers"} variant="quiet">Cancel</LinkButton>
      </div>
    </form>
  );
}
