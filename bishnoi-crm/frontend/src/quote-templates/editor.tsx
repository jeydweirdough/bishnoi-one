"use client";

import { AlertTriangle, CheckCircle2, Download } from "lucide-react";
import { FileDrop } from "@/src/platform/ui/file-drop";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { saveTemplate, uploadTemplateFile } from "@/src/actions/quote-templates";
import { Button } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { TemplateImage } from "./images";
import type { QuoteTemplate, TemplateDesign, TemplateList } from "./types";

type Props = { initial: QuoteTemplate; options: Pick<TemplateList, "issuers" | "teams" | "placeholders"> };

/** One quotation template: who it's for, its control numbers, and its form
 *  (an uploaded Excel sheet, or fields designed here), logo and e-signature. */
export function TemplateEditor({ initial, options }: Props) {
  const router = useRouter();
  const [t, setT] = useState(initial);
  const [v, setV] = useState({
    name: initial.name,
    kind: initial.kind,
    payer: initial.payer ?? "",
    teamId: initial.teamId ?? "",
    isActive: initial.isActive,
    controlPrefix: initial.controlPrefix ?? "",
    controlNext: String(initial.controlNext),
    controlDigits: String(initial.controlDigits),
  });
  const [d, setD] = useState<TemplateDesign>(initial.design);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });
  const setDesign = (k: keyof TemplateDesign) => (e: { target: { value: string } }) => setD({ ...d, [k]: e.target.value });
  const digits = Math.min(8, Math.max(1, Number(v.controlDigits) || 4));
  const example = `${(v.controlPrefix || "Q").replace(/-+$/, "")}-${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}-${String(Number(v.controlNext) || 1).padStart(digits, "0")}`;

  function save() {
    const next = Number(v.controlNext);
    if (!Number.isInteger(next) || next < 1) return setError("The next control number is a whole number, 1 or more.");
    start(async () => {
      const r = await saveTemplate(t.id, {
        name: v.name.trim(),
        kind: v.kind,
        payer: v.payer || null,
        teamId: v.teamId || null,
        isActive: v.isActive,
        controlPrefix: v.controlPrefix.trim() || null,
        controlNext: next,
        controlDigits: digits,
        design: d,
      });
      if (!r.ok) return setError(r.error);
      setError(null);
      setT(r.data);
      toast.success("Template saved");
      router.refresh();
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
      className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start"
    >
      <div className="space-y-5">
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="quotes">Template</SectionTitle>
          <div className="mt-3 grid gap-5 sm:grid-cols-2">
            <Field label="Name" className="sm:col-span-2">
              {(p) => <Input {...p} value={v.name} onChange={set("name")} maxLength={120} />}
            </Field>
            <Field label="Used for" hint="Quotes paid this way offer this template first.">
              {(p) => (
                <Select {...p} value={v.payer} onChange={set("payer")}>
                  <option value="">Any quote</option>
                  <option value="self">Quotes the customer pays</option>
                  {options.issuers.map((i) => (
                    <option key={i.code} value={i.code}>
                      {i.name} guarantee letters
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Team" hint="For example, a Getmeds team and a 2MG team with their own forms.">
              {(p) => (
                <Select {...p} value={v.teamId} onChange={set("teamId")}>
                  <option value="">Any team</option>
                  {options.teams.map((tm) => (
                    <option key={tm.id} value={tm.id}>
                      {tm.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <div className="sm:col-span-2">
              <Choice
                name="kind"
                legend="How it is made"
                value={v.kind}
                onChange={(kind) => setV({ ...v, kind })}
                options={[
                  { value: "excel", label: "Uploaded Excel form" },
                  { value: "form", label: "Designed here" },
                ]}
              />
            </div>
            <label className="flex items-center gap-2 text-sm sm:col-span-2">
              <input type="checkbox" checked={v.isActive} onChange={(e) => setV({ ...v, isActive: e.target.checked })} className="size-4 accent-hema" />
              In use (reps can print with it)
            </label>
          </div>
        </Sheet>

        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="lists">Control number</SectionTitle>
          <p className="text-meta text-ink-3">Each quote gets one the first time it is printed or downloaded with this template, and keeps it.</p>
          <div className="mt-3 grid gap-5 sm:grid-cols-3">
            <Field label="Starts with" hint="For example PCSOG or OPG.">
              {(p) => <Input {...p} value={v.controlPrefix} onChange={set("controlPrefix")} maxLength={20} className="uppercase" />}
            </Field>
            <Field label="Next number" hint="Continue from your current tracker.">
              {(p) => <Input {...p} inputMode="numeric" value={v.controlNext} onChange={set("controlNext")} />}
            </Field>
            <Field label="Digits">
              {(p) => <Input {...p} inputMode="numeric" value={v.controlDigits} onChange={set("controlDigits")} />}
            </Field>
          </div>
          <p className="mt-2 text-sm text-ink-2">
            Next one: <strong className="tabular-nums">{example}</strong>
          </p>
        </Sheet>

        {v.kind === "excel" ? (
          <ExcelForm template={t} onSaved={setT} placeholders={options.placeholders} />
        ) : (
          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle icon="company">Letterhead and wording</SectionTitle>
            <p className="text-meta text-ink-3">
              Left blank, the company name, address, TIN and contact come from Settings, Company and quotes. Write {"{issuer}"} where the issuer&apos;s
              name goes.
            </p>
            <div className="mt-3 grid gap-5 sm:grid-cols-2">
              <Field label="Company name" optional>
                {(p) => <Input {...p} value={d.companyName} onChange={setDesign("companyName")} />}
              </Field>
              <Field label="Check payable to" optional>
                {(p) => <Input {...p} value={d.payableTo} onChange={setDesign("payableTo")} />}
              </Field>
              <Field label="Address" optional className="sm:col-span-2">
                {(p) => <Textarea {...p} rows={2} value={d.address} onChange={setDesign("address")} />}
              </Field>
              <Field label="Telephone and mobile" optional>
                {(p) => <Input {...p} value={d.phone} onChange={setDesign("phone")} />}
              </Field>
              <Field label="TIN" optional>
                {(p) => <Input {...p} value={d.tin} onChange={setDesign("tin")} placeholder="000-000-000-00000" />}
              </Field>
              <div className="sm:col-span-2">
                <Choice
                  name="vat"
                  legend="Tax"
                  value={d.vat}
                  onChange={(vat) => setD({ ...d, vat })}
                  options={[
                    { value: "vat", label: "VAT" },
                    { value: "non_vat", label: "Non-VAT" },
                  ]}
                />
              </div>
              <Field label="Title" optional>
                {(p) => <Input {...p} value={d.heading} onChange={setDesign("heading")} />}
              </Field>
              <Field label="Customer is called" optional hint="For example Patient name or Beneficiary.">
                {(p) => <Input {...p} value={d.customerLabel} onChange={setDesign("customerLabel")} />}
              </Field>
              <Field label="Certification" optional className="sm:col-span-2">
                {(p) => <Textarea {...p} rows={3} value={d.certification} onChange={setDesign("certification")} />}
              </Field>
              <Field label="Guarantee letter statement" optional className="sm:col-span-2">
                {(p) => <Input {...p} value={d.acceptance} onChange={setDesign("acceptance")} />}
              </Field>
              <Field label="Notes at the bottom" optional className="sm:col-span-2">
                {(p) => <Textarea {...p} rows={3} value={d.notes} onChange={setDesign("notes")} />}
              </Field>
            </div>
          </Sheet>
        )}
      </div>

      <div className="space-y-5">
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="company">Logo</SectionTitle>
          <div className="mt-2">
            <TemplateImage template={t} which="logo" onSaved={setT} />
          </div>
        </Sheet>
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="approvals">E-signature</SectionTitle>
          <div className="mt-2">
            <TemplateImage template={t} which="signature" onSaved={setT} />
          </div>
          <div className="mt-4 grid gap-4 border-t border-rule pt-4">
            <Field label="Authorized representative" optional hint={v.kind === "excel" ? "Replaces the name under the signature line, if given." : undefined}>
              {(p) => <Input {...p} value={d.signatoryName} onChange={setDesign("signatoryName")} />}
            </Field>
            <Field label="Designation" optional>
              {(p) => <Input {...p} value={d.signatoryTitle} onChange={setDesign("signatoryTitle")} />}
            </Field>
            <Field label="Contact number" optional>
              {(p) => <Input {...p} value={d.signatoryContact} onChange={setDesign("signatoryContact")} />}
            </Field>
          </div>
        </Sheet>
      </div>

      <div className="lg:col-span-2">
        <FormError message={error} />
        <Button type="submit" variant="primary" loading={pending} className="mt-2">
          Save template
        </Button>
      </div>
    </form>
  );
}

/** The uploaded Excel form: which sheet, and what the CRM found on it. */
function ExcelForm({ template, onSaved, placeholders }: { template: QuoteTemplate; onSaved: (t: QuoteTemplate) => void; placeholders: { key: string; label: string }[] }) {
  const [pending, start] = useTransition();
  const excel = template.excel;

  function upload(f: File) {
    const form = new FormData();
    form.set("file", f);
    start(async () => {
      const r = await uploadTemplateFile(template.id, "excel", form);
      if (!r.ok) return void toast.error("The form wasn't uploaded", { description: r.error });
      onSaved(r.data);
      toast.success("Form uploaded", { description: r.data.excel?.missing.length ? "Check what wasn't found." : "Everything was found." });
    });
  }

  function pickSheet(sheet: string) {
    start(async () => {
      const r = await saveTemplate(template.id, { excelSheet: sheet });
      if (!r.ok) return void toast.error("Not changed", { description: r.error });
      onSaved(r.data);
    });
  }

  return (
    <Sheet className="px-5 pt-4 pb-5">
      <SectionTitle
        icon="lists"
        action={
          excel && (
            <a href={`/admin/settings/quote-templates/${template.id}/form`} className="inline-flex items-center gap-1 text-meta font-medium text-ink hover:underline">
              <Download className="size-3.5" aria-hidden />
              Download the form
            </a>
          )
        }
      >
        Excel form
      </SectionTitle>
      <p className="text-meta text-ink-3">
        Upload your quotation sheet as it is. The CRM finds the patient name, contact number, address, hospital, date issued, control number, the
        products table, the grand total and the signature line by their labels, and fills them in for each quote.
      </p>
      <div className="mt-3">
        <FileDrop
          accept=".xlsx,.xlsm"
          note={excel ? "Drop another to replace it. Excel (.xlsx)" : "Your quotation sheet in Excel (.xlsx)"}
          busy={pending}
          keep
          current={excel ? { name: excel.name } : null}
          onFile={(f) => f && upload(f)}
        />
      </div>

      {excel && (
        <div className="mt-4 space-y-4 border-t border-rule pt-4">
          {excel.sheets.length > 1 && (
            <Field label="Sheet with the quotation form" hint="Only this sheet is filled in and downloaded.">
              {(p) => (
                <Select {...p} value={excel.sheet} onChange={(e) => pickSheet(e.target.value)} disabled={pending}>
                  {excel.sheets.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
          <div>
            <p className="mb-1 text-meta font-medium text-ink-2">Found on the sheet</p>
            <ul className="space-y-0.5 text-sm">
              {excel.found.map((f) => (
                <li key={f} className="flex items-start gap-2">
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-filed" aria-hidden />
                  {f}
                </li>
              ))}
              {excel.missing.map((m) => (
                <li key={m} className="flex items-start gap-2 text-danger">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
                  {m}: not found. Put a label beside it, or a placeholder in the cell (below).
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <details className="mt-4 border-t border-rule pt-3">
        <summary className="cursor-pointer text-meta font-medium text-ink">Placeholders, for cells the labels don&apos;t cover</summary>
        <p className="mt-2 text-meta text-ink-3">
          Type one in a cell of the form to say exactly what goes there, for example {"{{customer}}"}. For the products table, put the line placeholders in
          one row; it repeats for each product.
        </p>
        <table className="mt-2 w-full text-meta">
          <tbody className="divide-y divide-rule">
            {placeholders.map((p) => (
              <tr key={p.key}>
                <td className="py-1 pr-3 font-mono text-ink">{`{{${p.key}}}`}</td>
                <td className="py-1 text-ink-2">{p.label}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </Sheet>
  );
}
