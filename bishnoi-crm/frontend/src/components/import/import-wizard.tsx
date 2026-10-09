"use client";

import { ArrowRight, CheckCircle2, FileSpreadsheet, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { FileDrop } from "@/src/platform/ui/file-drop";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { readImport, runImport, type ImportFile, type ImportKind, type ImportResult } from "../../actions/imports";

const WORDS: Record<ImportKind, { one: string; many: string; match: string }> = {
  products: { one: "product", many: "products", match: "A product already here (same code) is updated; the rest are added." },
  people: { one: "person", many: "people", match: "Someone already here (same email) is updated; the rest are added as new accounts." },
  customers: {
    one: "customer",
    many: "customers",
    match: "A row with a customer code updates that customer; a row without one is added as new. Pick lists take the short code or the full name; a hospital, by its name or code.",
  },
  balances: {
    one: "balance",
    many: "balances",
    match: "Each row is matched to its customer by name. The balances are added as of the date below; earlier ones stay as the history.",
  },
};

/** Today in the browser, as YYYY-MM-DD: where "as of" starts. */
const today = () => new Date().toLocaleDateString("en-CA");

/**
 * Importing from a spreadsheet, in three steps: pick the file, match its
 * columns to our fields, then check and import. Nothing is saved before the
 * last button; the check says, row by row, what would go wrong.
 */
export function ImportWizard({ kind, back }: { kind: ImportKind; back: string }) {
  const router = useRouter();
  const words = WORDS[kind];
  const [file, setFile] = useState<ImportFile | null>(null);
  const [mapping, setMapping] = useState<Record<string, number | null>>({});
  const [password, setPassword] = useState("");
  const [makeTeams, setMakeTeams] = useState(true);
  const [asOf, setAsOf] = useState(today);
  const [check, setCheck] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function read(form: FormData) {
    start(async () => {
      const r = await readImport(kind, form);
      if (!r.ok) return setError(r.error);
      setFile(r.data);
      setMapping(r.data.mapping);
      setCheck(null);
      setError(null);
    });
  }

  function run(dryRun: boolean) {
    if (!file) return;
    start(async () => {
      const r = await runImport(kind, {
        mapping,
        rows: file.rows,
        dryRun,
        ...(kind === "people" ? { password: password || null, makeTeams } : {}),
        ...(kind === "balances" ? { asOf } : {}),
      });
      if (!r.ok) return setError(r.error);
      setError(null);
      if (dryRun) return setCheck(r.data);
      const { added, updated, problems } = r.data;
      toast.success(kind === "balances" ? `${added} balances added` : `${added} added, ${updated} updated`, { description: problems.length ? `${problems.length} rows skipped: see the list.` : `All ${words.many} imported.` });
      setCheck({ ...r.data });
      if (!problems.length) router.push(back);
      router.refresh();
    });
  }

  const map = (key: string, value: string) => {
    setMapping({ ...mapping, [key]: value === "" ? null : Number(value) });
    setCheck(null); // a new mapping needs a new check
  };
  const first = file?.rows[0] ?? [];
  const used = new Set(Object.values(mapping).filter((v): v is number => v !== null));
  const unused = file ? file.headers.filter((_, i) => !used.has(i)) : [];
  const ready = file && file.fields.filter((f) => f.required).every((f) => mapping[f.key] !== null && mapping[f.key] !== undefined);

  return (
    <div className="space-y-5">
      <Sheet className="px-5 pt-4 pb-5">
        <SectionTitle icon="lists">1 · The file</SectionTitle>
        <p className="text-meta text-ink-3">
          An Excel workbook (.xlsx, first sheet) or a CSV, with a header row on top. {words.match}
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            read(new FormData(e.currentTarget));
          }}
          className="mt-3 space-y-3"
        >
          <Field label="Spreadsheet">
            {(p) => (
              <FileDrop
                {...p}
                name="file"
                accept=".xlsx,.xlsm,.csv"
                note="Excel (.xlsx) or CSV, with the column names in the first row"
                busy={pending && !file}
                onChange={(e) => e.currentTarget.form?.requestSubmit()}
              />
            )}
          </Field>
          <div className="flex justify-end">
          <Button type="submit" loading={pending && !file} icon={<FileSpreadsheet className="size-4" aria-hidden />}>
            Read file
          </Button>
          </div>
        </form>
        {kind === "customers" && !file && (
          <p className="mt-3 text-meta text-ink-3">
            Starting from nothing?{" "}
            <a href="/companies/export?template=true" download className="font-semibold text-ink underline">
              Download a blank sheet
            </a>{" "}
            with our columns. To change many customers at once, export them from Customers, edit the file, and import it here.
          </p>
        )}
        {file && (
          <p className="mt-3 text-sm text-ink-2">
            <strong>{file.fileName}</strong>: {file.rows.length} {file.rows.length === 1 ? "row" : "rows"}, {file.headers.length} columns.
          </p>
        )}
      </Sheet>

      {file && (
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="particulars">2 · Match the columns</SectionTitle>
          <p className="text-meta text-ink-3">Each of our fields on the left, and which column of your file fills it. They&apos;re matched from the headers; change any that are wrong.</p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[40rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th scope="col" className="py-2 pr-3 font-semibold">Our field</th>
                  <th scope="col" className="px-3 py-2 font-semibold">Column in your file</th>
                  <th scope="col" className="py-2 pl-3 font-semibold">First row</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {file.fields.map((f) => {
                  const col = mapping[f.key];
                  return (
                    <tr key={f.key}>
                      <th scope="row" className="py-2 pr-3 text-left font-medium">
                        {f.label}
                        {f.required && <span className="text-danger"> *</span>}
                      </th>
                      <td className="px-3 py-2">
                        <Select
                          aria-label={`Column for ${f.label}`}
                          value={col ?? ""}
                          onChange={(e) => map(f.key, e.target.value)}
                          className={`h-9 w-full border-0 border-b bg-transparent text-sm focus:border-hema focus:outline-none ${f.required && (col === null || col === undefined) ? "border-danger" : "border-control"}`}
                        >
                          <option value="">— Not in the file —</option>
                          {file.headers.map((h, i) => (
                            <option key={i} value={i}>
                              {h}
                            </option>
                          ))}
                        </Select>
                      </td>
                      <td className="max-w-64 truncate py-2 pl-3 text-ink-2">{col !== null && col !== undefined ? first[col] || <span className="text-ink-3">empty</span> : <span className="text-ink-3">—</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {unused.length > 0 && <p className="mt-2 text-meta text-ink-3">Left out: {unused.join(", ")}.</p>}
          {kind === "balances" && (
            <div className="mt-4 grid gap-4 border-t border-rule pt-4 sm:grid-cols-2">
              <Field label="Balances as of" hint="Accounting's cut-off date. Collections logged after it come off these balances.">
                {(p) => <Input {...p} type="date" value={asOf} max={today()} onChange={(e) => (setAsOf(e.target.value), setCheck(null))} />}
              </Field>
            </div>
          )}
          {kind === "people" && (
            <div className="mt-4 grid gap-4 border-t border-rule pt-4 sm:grid-cols-2">
              <Field label="First password for new accounts" hint="At least 8 characters. Give it to them yourself; they change it under Account.">
                {(p) => <Input {...p} type="password" value={password} onChange={(e) => (setPassword(e.target.value), setCheck(null))} autoComplete="new-password" />}
              </Field>
              <label className="flex items-center gap-2 self-center text-sm">
                <input type="checkbox" checked={makeTeams} onChange={(e) => (setMakeTeams(e.target.checked), setCheck(null))} className="size-4 accent-hema" />
                Make the teams that aren&apos;t here yet
              </label>
            </div>
          )}
        </Sheet>
      )}

      {file && (
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="approvals">3 · Check, then import</SectionTitle>
          {check ? (
            <div className="mt-2 space-y-3">
              <p className="flex items-center gap-2 text-sm">
                <CheckCircle2 className="size-4 text-filed" aria-hidden />
                {check.dryRun ? "Ready:" : "Done:"} {check.added} {check.added === 1 ? words.one : words.many} {check.dryRun ? "to add" : "added"}, {check.updated}{" "}
                {check.dryRun ? "to update" : "updated"}.
              </p>
              {check.problems.length > 0 && (
                <div className="rounded-[14px] border border-danger/40 bg-danger-tint/40 px-4 py-3">
                  <p className="flex items-center gap-2 text-sm font-semibold text-danger">
                    <TriangleAlert className="size-4" aria-hidden />
                    {check.problems.length} {check.problems.length === 1 ? "row is" : "rows are"} {check.dryRun ? "skipped unless you fix them" : "skipped"}
                  </p>
                  <ul className="mt-2 max-h-64 space-y-0.5 overflow-y-auto text-meta text-ink-2">
                    {check.problems.map((p) => (
                      <li key={`${p.row}-${p.message}`}>
                        <span className="font-semibold">Row {p.row}:</span> {p.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <p className="mt-1 text-meta text-ink-3">Check first: it goes through every row and saves nothing.</p>
          )}
          <FormError message={error} />
          <div className="mt-4 flex flex-wrap gap-2">
            <Button onClick={() => run(true)} loading={pending && !!file} disabled={!ready}>
              Check {file.rows.length} rows
            </Button>
            <Button
              variant="primary"
              onClick={() => run(false)}
              disabled={!check || !check.dryRun || check.added + check.updated === 0}
              icon={<ArrowRight className="size-4" aria-hidden />}
            >
              Import {check && check.dryRun ? check.added + check.updated : ""} {words.many}
            </Button>
            <LinkButton href={back} variant="quiet">
              {check && !check.dryRun ? "Done" : "Cancel"}
            </LinkButton>
          </div>
          {!ready && <p className="mt-2 text-meta text-danger">Pick a column for each field marked *.</p>}
        </Sheet>
      )}
      {!file && <FormError message={error} />}
    </div>
  );
}
