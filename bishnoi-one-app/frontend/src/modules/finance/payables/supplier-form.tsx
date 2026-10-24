"use client";

import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { CellInput, Choice, Field, FormError, Input, Select, Textarea } from "@/src/modules/finance/platform/ui/field";
import { formatTin } from "@/src/modules/finance/lib/tin";
import { saveSupplier, switchSupplier } from "@/src/modules/finance/payables/actions";
import type { Supplier, SupplierContact, Withholding } from "@/src/modules/finance/payables/types";

const SALUTATIONS = ["Mr.", "Ms.", "Mrs.", "Dr.", "Engr.", "Atty."];
const blankContact = (): SupplierContact => ({ salutation: null, firstName: null, lastName: null, email: null, phone: null, mobile: null, designation: null });
type Account = { id: string; code: string; name: string };

/**
 * A supplier, the way Zoho's New Vendor reads (your screenshots, 2026-10-23): the primary
 * contact, the company and how it's shown, email and phones; then the details a bill needs
 * (VAT, the tax usually withheld, terms, which payables account), the other people there,
 * and where they're paid. Each new bill from them fills these in (Aubrey Q11). Zoho's
 * Company ID is the TIN here.
 */
export function SupplierForm({ supplier, withholding, accounts }: { supplier: Supplier | null; withholding: Withholding[]; accounts: Account[] }) {
  const router = useRouter();
  const [v, setV] = useState({
    salutation: supplier?.salutation ?? "",
    firstName: supplier?.firstName ?? "",
    lastName: supplier?.lastName ?? "",
    companyName: supplier?.companyName ?? "",
    name: supplier?.name ?? "",
    email: supplier?.email ?? "",
    phone: supplier?.phone ?? "",
    mobile: supplier?.mobile ?? "",
    tin: formatTin(supplier?.tin ? `${supplier.tin}${supplier.branchCode ?? ""}` : ""),
    address: supplier?.address ?? "",
    vat: supplier ? (supplier.vatRegistered ? "yes" : "no") : "yes",
    withholding: supplier?.withholding?.code ?? "",
    terms: String(supplier?.termsDays ?? 30),
    payablesAccountId: supplier?.payablesAccount?.id ?? "",
    bankName: supplier?.bankName ?? "",
    bankAccountName: supplier?.bankAccountName ?? "",
    bankAccountNumber: supplier?.bankAccountNumber ?? "",
    notes: supplier?.notes ?? "",
  });
  const [contacts, setContacts] = useState<SupplierContact[]>(supplier?.contacts.length ? supplier.contacts : []);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const set = (patch: Partial<typeof v>) => setV({ ...v, ...patch });
  const blank = (s: string) => s.trim() || null;
  const setContact = (i: number, patch: Partial<SupplierContact>) => setContacts(contacts.map((c, n) => (n === i ? { ...c, ...patch } : c)));

  function submit(e: React.FormEvent) {
    e.preventDefault();
    // Like Zoho, the display name can come from the company name when it's left empty.
    const name = v.name.trim() || v.companyName.trim();
    if (!name) {
      setFields({ name: "Enter how the supplier is shown, or their company name." });
      setError("Please review the highlighted fields.");
      return;
    }
    start(async () => {
      const result = await saveSupplier(supplier?.id ?? null, {
        name,
        companyName: blank(v.companyName),
        salutation: v.salutation || null,
        firstName: blank(v.firstName),
        lastName: blank(v.lastName),
        tin: blank(v.tin),
        branchCode: null,
        address: blank(v.address),
        vatRegistered: v.vat === "yes",
        withholding: v.withholding || null,
        termsDays: Number(v.terms) || 0,
        email: blank(v.email),
        phone: blank(v.phone),
        mobile: blank(v.mobile),
        payablesAccountId: v.payablesAccountId || null,
        contacts: contacts.map((c) => Object.fromEntries(Object.entries(c).map(([k, x]) => [k, typeof x === "string" ? x.trim() || null : x])) as SupplierContact),
        bankName: blank(v.bankName),
        bankAccountName: blank(v.bankAccountName),
        bankAccountNumber: blank(v.bankAccountNumber),
        notes: blank(v.notes),
      });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(supplier ? "Supplier saved" : "Supplier added", { description: result.data.name });
      router.push(`/finance/suppliers/${result.data.id}`);
    });
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-6">
      <section className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-[8rem_minmax(0,1fr)_minmax(0,1fr)]">
          <Field label="Salutation" optional>
            {(p) => (
              <Select {...p} value={v.salutation} onChange={(e) => set({ salutation: e.target.value })}>
                <option value="" />
                {SALUTATIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Primary contact: first name" optional error={fields.firstName}>
            {(p) => <Input {...p} value={v.firstName} onChange={(e) => set({ firstName: e.target.value })} maxLength={80} />}
          </Field>
          <Field label="Last name" optional error={fields.lastName}>
            {(p) => <Input {...p} value={v.lastName} onChange={(e) => set({ lastName: e.target.value })} maxLength={80} />}
          </Field>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Company name" optional error={fields.companyName} hint="As registered (BIR, SEC or DTI).">
            {(p) => <Input {...p} value={v.companyName} onChange={(e) => set({ companyName: e.target.value })} maxLength={200} autoFocus={!supplier} />}
          </Field>
          <Field label="Display name" error={fields.name} hint="How they're shown in Finance. Left empty: the company name.">
            {(p) => <Input {...p} value={v.name} onChange={(e) => set({ name: e.target.value })} placeholder={v.companyName} maxLength={200} />}
          </Field>
          <Field label="Email" optional error={fields.email}>
            {(p) => <Input {...p} type="email" value={v.email} onChange={(e) => set({ email: e.target.value })} maxLength={254} />}
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Work phone" optional error={fields.phone}>
              {(p) => <Input {...p} value={v.phone} onChange={(e) => set({ phone: e.target.value })} maxLength={40} />}
            </Field>
            <Field label="Mobile" optional error={fields.mobile}>
              {(p) => <Input {...p} value={v.mobile} onChange={(e) => set({ mobile: e.target.value })} maxLength={40} />}
            </Field>
          </div>
        </div>
      </section>

      <section className="space-y-4 border-t border-rule pt-5">
        <p className="text-sm font-semibold">Tax, terms and books</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="TIN" optional error={fields.tin} hint="Zoho's Company ID. Digits only: the dashes go in by themselves; 9 digits, then the branch code if any.">
            {(p) => <Input {...p} inputMode="numeric" value={v.tin} onChange={(e) => set({ tin: formatTin(e.target.value) })} placeholder="123-456-789-00000" maxLength={17} />}
          </Field>
          <Field label="Address" optional error={fields.address}>
            {(p) => <Input {...p} value={v.address} onChange={(e) => set({ address: e.target.value })} maxLength={300} />}
          </Field>
        </div>
        <Choice
          name="vat"
          legend="Do they charge VAT?"
          value={v.vat}
          onChange={(vat) => set({ vat })}
          options={[
            { value: "yes", label: "VAT-registered" },
            { value: "no", label: "Not VAT-registered" },
          ]}
        />
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_10rem]">
          <Field label="Usual tax withheld" optional error={fields.withholding} hint="Filled in on each new bill from them; a line can use another. The 1% and 2% apply when the company is a top withholding agent.">
            {(p) => (
              <Select {...p} value={v.withholding} onChange={(e) => set({ withholding: e.target.value })}>
                <option value="">None</option>
                {withholding.map((w) => (
                  <option key={w.code} value={w.code}>
                    {w.code} · {w.name} · {w.rateBp / 100}%
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Payment terms (days)" error={fields.termsDays}>
            {(p) => <Input {...p} inputMode="numeric" value={v.terms} onChange={(e) => set({ terms: e.target.value.replace(/\D/g, "") })} maxLength={3} />}
          </Field>
        </div>
        <Field label="Accounts payable" optional error={fields.payablesAccountId} hint="Where their bills post what's owed. Left empty: the default (Accounting → Default accounts).">
          {(p) => (
            <Select {...p} value={v.payablesAccountId} onChange={(e) => set({ payablesAccountId: e.target.value })}>
              <option value="">The default</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} · {a.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </section>

      <section className="space-y-3 border-t border-rule pt-5">
        <p className="text-sm font-semibold">Contact persons</p>
        {contacts.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[52rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th className="w-24 py-1.5 pr-2 font-semibold">Salutation</th>
                  <th className="px-2 py-1.5 font-semibold">First name</th>
                  <th className="px-2 py-1.5 font-semibold">Last name</th>
                  <th className="px-2 py-1.5 font-semibold">Email</th>
                  <th className="px-2 py-1.5 font-semibold">Phone</th>
                  <th className="px-2 py-1.5 font-semibold">Position</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody>
                {contacts.map((c, i) => (
                  <tr key={i}>
                    <td className="py-1.5 pr-2">
                      <select aria-label={`Contact ${i + 1}: salutation`} value={c.salutation ?? ""} onChange={(e) => setContact(i, { salutation: e.target.value || null })} className="h-8 w-full rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm">
                        <option value="" />
                        {SALUTATIONS.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </td>
                    {(["firstName", "lastName", "email", "phone", "designation"] as const).map((k) => (
                      <td key={k} className="px-2 py-1.5">
                        <CellInput aria-label={`Contact ${i + 1}: ${k}`} value={c[k] ?? ""} onChange={(e) => setContact(i, { [k]: e.target.value })} maxLength={k === "email" ? 254 : 80} className="w-full !text-left" />
                      </td>
                    ))}
                    <td className="py-1.5">
                      <Button size="sm" variant="quiet" className="!px-1.5 !text-ink-3 hover:!text-danger" aria-label={`Remove contact ${i + 1}`} onClick={() => setContacts(contacts.filter((_, n) => n !== i))}>
                        <Trash2 className="size-4" aria-hidden />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Button size="sm" variant="quiet" className="-ml-3" icon={<Plus className="size-4" aria-hidden />} onClick={() => setContacts([...contacts, blankContact()])}>
          Add a contact person
        </Button>
      </section>

      <fieldset className="grid gap-4 border-t border-rule pt-5 sm:grid-cols-3">
        <legend className="mb-2 pt-5 text-sm font-semibold">Where they&apos;re paid</legend>
        <Field label="Bank" optional error={fields.bankName}>
          {(p) => <Input {...p} value={v.bankName} onChange={(e) => set({ bankName: e.target.value })} maxLength={80} placeholder="BDO" />}
        </Field>
        <Field label="Account name" optional error={fields.bankAccountName}>
          {(p) => <Input {...p} value={v.bankAccountName} onChange={(e) => set({ bankAccountName: e.target.value })} maxLength={120} />}
        </Field>
        <Field label="Account number" optional error={fields.bankAccountNumber}>
          {(p) => <Input {...p} value={v.bankAccountNumber} onChange={(e) => set({ bankAccountNumber: e.target.value })} maxLength={40} />}
        </Field>
      </fieldset>
      <Field label="Remarks" optional error={fields.notes}>
        {(p) => <Textarea {...p} value={v.notes} onChange={(e) => set({ notes: e.target.value })} maxLength={500} />}
      </Field>
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {supplier ? "Save supplier" : "Add supplier"}
        </Button>
        <Button type="button" variant="quiet" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

/** Switching a supplier off (not offered on new bills; their bills stay) or back on: its own tick. */
export function SwitchSupplier({ id, isActive }: { id: string; isActive: boolean }) {
  const [pending, start] = useTransition();
  return (
    <Button
      loading={pending}
      onClick={() =>
        start(async () => {
          const result = await switchSupplier(id, !isActive);
          if (!result.ok) return void toast.error(result.error);
          toast.success(isActive ? "Supplier switched off" : "Supplier switched back on", { description: isActive ? "Not offered on new bills; their bills stay as they are." : undefined });
        })
      }
    >
      {isActive ? "Switch off" : "Switch back on"}
    </Button>
  );
}
