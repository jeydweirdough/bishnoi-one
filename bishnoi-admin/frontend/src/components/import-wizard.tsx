"use client";

import { ArrowRight, CheckCircle2, Download, FileSpreadsheet, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Field, FileInput, FormError } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { readImport, runImport, type ImportFile, type ImportKind, type ImportResult } from "../actions/imports";
import { IMPORTS } from "./import-words";

/**
 * Importing from a spreadsheet, in three steps: choose the file, match its
 * columns to our fields, then check and import. Nothing is saved before the
 * last button; the check says, row by row, what would go wrong.
 */
export function ImportWizard({ kind }: { kind: ImportKind }) {
  const router = useRouter();
  const words = IMPORTS[kind];
  const [file, setFile] = useState<ImportFile | null>(null);
  const [mapping, setMapping] = useState<Record<string, number | null>>({});
  const [check, setCheck] = useState<(ImportResult & { dryRun: boolean }) | null>(null);
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
      const r = await runImport(kind, { mapping, rows: file.rows, dryRun });
      if (!r.ok) return setError(r.error);
      setError(null);
      setCheck({ ...r.data, dryRun });
      if (dryRun) return;
      const { added, updated, problems } = r.data;
      toast.success(`${added} added, ${updated} updated`, {
        description: problems.length ? `${problems.length} rows skipped. See the list.` : `All ${words.many} imported.`,
      });
      if (!problems.length) router.push(words.back);
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
        <SectionTitle
          icon="lists"
          action={
            <a href={`/files/template/${kind}`} download className="inline-flex items-center gap-1 text-meta font-medium text-hema hover:underline">
              <Download className="size-3.5" aria-hidden />
              Download template
            </a>
          }
        >
          1. Choose the file
        </SectionTitle>
        <p className="text-meta text-ink-3">
          An Excel workbook (.xlsx, first sheet) or a CSV file, with the column names in the first row. A report exported from this page can be
          edited and imported back. {words.match}
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            read(new FormData(e.currentTarget));
          }}
          className="mt-3 flex flex-wrap items-end gap-3"
        >
          <Field label="Spreadsheet" className="min-w-64 flex-1">
            {(p) => <FileInput {...p} name="file" accept=".xlsx,.xlsm,.csv" onChange={(e) => e.currentTarget.form?.requestSubmit()} />}
          </Field>
          <Button type="submit" loading={pending && !file} icon={<FileSpreadsheet className="size-4" aria-hidden />}>
            Read file
          </Button>
        </form>
        {file && (
          <p className="mt-3 text-sm text-ink-2">
            <strong>{file.fileName}</strong>: {file.rows.length} {file.rows.length === 1 ? "row" : "rows"}, {file.headers.length} columns.
          </p>
        )}
      </Sheet>

      {file && (
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="particulars">2. Match the columns</SectionTitle>
          <p className="text-meta text-ink-3">
            Each field on the left, and the column in your file that fills it. They are matched by the column names; change any that are wrong.
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[40rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-meta text-ink-3">
                  <th scope="col" className="py-2 pr-3 font-semibold">Field</th>
                  <th scope="col" className="px-3 py-2 font-semibold">Column in your file</th>
                  <th scope="col" className="py-2 pl-3 font-semibold">First row</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {file.fields.map((f) => {
                  const col = mapping[f.key];
                  const missing = f.required && (col === null || col === undefined);
                  return (
                    <tr key={f.key}>
                      <th scope="row" className="py-2 pr-3 text-left align-top font-medium">
                        {f.label}
                        {f.required && <span className="text-danger"> *</span>}
                        {f.hint && <span className="block text-meta font-normal text-ink-3">{f.hint}</span>}
                      </th>
                      <td className="px-3 py-2 align-top">
                        <select
                          aria-label={`Column for ${f.label}`}
                          value={col ?? ""}
                          onChange={(e) => map(f.key, e.target.value)}
                          className={`h-9 w-full border-0 border-b bg-transparent text-sm focus:border-hema focus:outline-none ${missing ? "border-danger" : "border-control"}`}
                        >
                          <option value="">Not in the file</option>
                          {file.headers.map((h, i) => (
                            <option key={i} value={i}>
                              {h}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="max-w-64 truncate py-2 pl-3 align-top text-ink-2">
                        {col !== null && col !== undefined ? first[col] || <span className="text-ink-3">Empty</span> : <span className="text-ink-3">None</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {unused.length > 0 && <p className="mt-2 text-meta text-ink-3">Not imported: {unused.join(", ")}.</p>}
        </Sheet>
      )}

      {file && (
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="approvals">3. Check, then import</SectionTitle>
          {check ? (
            <div className="mt-2 space-y-3">
              <p className="flex items-center gap-2 text-sm">
                <CheckCircle2 className="size-4 text-filed" aria-hidden />
                {check.dryRun ? "Ready:" : "Done:"} {check.added} {check.added === 1 ? words.one : words.many} {check.dryRun ? "to add" : "added"},{" "}
                {check.updated} {check.dryRun ? "to update" : "updated"}.
              </p>
              {check.unmapped.length > 0 && check.dryRun && (
                <p className="text-meta text-ink-3">
                  Not in the file: {check.unmapped.join(", ")}. New records take the usual default; records already here keep what they have.
                </p>
              )}
              {check.problems.length > 0 && (
                <div className="rounded-[12px] border border-danger/40 bg-danger-tint/40 px-4 py-3">
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
            <p className="mt-1 text-meta text-ink-3">Check first. It goes through every row and saves nothing.</p>
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
            <LinkButton href={words.back} variant="quiet">
              {check && !check.dryRun ? "Done" : "Cancel"}
            </LinkButton>
          </div>
          {!ready && <p className="mt-2 text-meta text-danger">Choose a column for each field marked *.</p>}
        </Sheet>
      )}
      {!file && <FormError message={error} />}
    </div>
  );
}
