"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Choice, Field, FormError, Input, Textarea } from "@/src/modules/finance/platform/ui/field";
import { saveTaxProfile } from "@/src/modules/finance/tax/actions";
import type { TaxSetup } from "@/src/modules/finance/tax/types";

/** The company's tax registration, as every invoice has to state it. */
export function RegistrationForm({ setup }: { setup: TaxSetup }) {
  const p = setup.profile;
  const [pending, start] = useTransition();
  const [v, setV] = useState({
    regime: p.regime,
    registeredName: p.registeredName ?? "",
    tradeName: p.tradeName ?? "",
    tin: p.tin ?? "",
    branchCode: p.branchCode,
    registeredAddress: p.registeredAddress ?? "",
    pricesIncludeTax: p.pricesIncludeTax ? "yes" : "no",
    rdoCode: p.rdoCode ?? "",
    fiscalMonthEnd: String(p.fiscalMonthEnd ?? 12),
  });
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const set = (change: Partial<typeof v>) => setV({ ...v, ...change });
  const locked = !setup.canEdit;

  function submit() {
    start(async () => {
      const result = await saveTaxProfile({
        country: p.country,
        regime: v.regime,
        registeredName: v.registeredName.trim() || null,
        tradeName: v.tradeName.trim() || null,
        tin: v.tin.trim() || null,
        branchCode: v.branchCode.trim() || null,
        registeredAddress: v.registeredAddress.trim() || null,
        pricesIncludeTax: v.pricesIncludeTax === "yes",
        rdoCode: v.rdoCode.trim() || null,
        fiscalMonthEnd: Number(v.fiscalMonthEnd),
      });
      if (result.ok) {
        toast.success("Tax registration saved");
        setError(null);
        setFields({});
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
        submit();
      }}
      className="space-y-6"
    >
      <fieldset disabled={locked} className="space-y-6">
        <Choice
          name="regime"
          legend="Tax registration type"
          value={v.regime}
          onChange={(regime) => set({ regime })}
          options={setup.pack.regimes.map((r) => ({ value: r.key, label: r.name }))}
        />
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Registered name" error={fields.registeredName} hint="Exactly as on the BIR Certificate of Registration.">
            {(f) => <Input {...f} value={v.registeredName} onChange={(e) => set({ registeredName: e.target.value })} />}
          </Field>
          <Field label="Trade name" optional>
            {(f) => <Input {...f} value={v.tradeName} onChange={(e) => set({ tradeName: e.target.value })} />}
          </Field>
          <Field label="TIN" error={fields.tin} hint="9 digits, e.g. 123-456-789.">
            {(f) => <Input {...f} inputMode="numeric" value={v.tin} onChange={(e) => set({ tin: e.target.value })} placeholder="123-456-789" />}
          </Field>
          <Field label="Branch code" error={fields.branchCode} hint="00000 for the head office.">
            {(f) => <Input {...f} inputMode="numeric" value={v.branchCode} onChange={(e) => set({ branchCode: e.target.value.replace(/\D/g, "") })} />}
          </Field>
          <Field label="RDO code" error={fields.rdoCode} hint="3 digits, from the certificate of registration (Form 2303). On every BIR form.">
            {(f) => <Input {...f} inputMode="numeric" maxLength={3} value={v.rdoCode} onChange={(e) => set({ rdoCode: e.target.value.replace(/\D/g, "") })} />}
          </Field>
          <Field label="Fiscal year ends in" error={fields.fiscalMonthEnd} hint="December for a calendar year. The BIR returns' quarters follow it.">
            {(f) => (
              <select {...f} value={v.fiscalMonthEnd} onChange={(e) => set({ fiscalMonthEnd: e.target.value })} className="h-9 w-full rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm">
                {["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"].map((m, i) => (
                  <option key={m} value={i + 1}>
                    {m}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Registered address" error={fields.registeredAddress} className="sm:col-span-2">
            {(f) => <Textarea {...f} value={v.registeredAddress} onChange={(e) => set({ registeredAddress: e.target.value })} maxLength={300} />}
          </Field>
        </div>
        <Choice
          name="inclusive"
          legend="Catalogue prices"
          value={v.pricesIncludeTax}
          onChange={(pricesIncludeTax) => set({ pricesIncludeTax })}
          options={[
            { value: "yes", label: "VAT-inclusive (shelf prices)" },
            { value: "no", label: "VAT-exclusive" },
          ]}
        />
      </fieldset>
      <FormError message={error} />
      {locked ? (
        <p className="text-meta text-ink-3">Only Finance administrators can change the registration.</p>
      ) : (
        <Button type="submit" variant="primary" loading={pending}>
          Save registration
        </Button>
      )}
    </form>
  );
}
