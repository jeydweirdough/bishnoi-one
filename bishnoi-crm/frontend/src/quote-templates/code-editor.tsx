"use client";

import { useEffect, useRef, useState } from "react";
import { codeFields, previewCode } from "@/src/actions/quote-templates";
import { Button } from "@/src/platform/ui/button";
import { Input } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import type { CodeFields } from "./types";

// A quotation written as code: the company's own HTML and styles, with
// %fields% where the quote's details go, beside a live preview of it filled in
// with the template's latest quote (or made-up values when there's none yet).
// The CRM cleans the code before it shows or prints it: scripts, frames, forms
// and outside links are taken out; styles and pictures stay.

const WAIT_MS = 600; // after the last key, then the preview catches up

export function CodeTemplate({ templateId, html, onChange }: { templateId: string; html: string; onChange: (html: string) => void }) {
  const [fields, setFields] = useState<CodeFields | null>(null);
  const [filter, setFilter] = useState("");
  const [preview, setPreview] = useState<{ html: string; using: string } | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const area = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    codeFields().then((r) => (r.ok ? setFields(r.data) : setProblem(r.error)));
  }, []);

  useEffect(() => {
    let live = true;
    const t = setTimeout(async () => {
      setBusy(true);
      const r = await previewCode(templateId, html);
      if (!live) return;
      setBusy(false);
      if (r.ok) {
        setPreview(r.data);
        setProblem(null);
      } else setProblem(r.error);
    }, WAIT_MS);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [templateId, html]);

  /** Puts text where the cursor is (or over the selection), and keeps the cursor after it. */
  function insert(text: string) {
    const el = area.current;
    const at = el?.selectionStart ?? html.length;
    const to = el?.selectionEnd ?? at;
    onChange(html.slice(0, at) + text + html.slice(to));
    requestAnimationFrame(() => {
      if (!el) return;
      el.focus();
      el.setSelectionRange(at + text.length, at + text.length);
    });
  }

  const wanted = filter.trim().toLowerCase();
  const groups = (fields?.groups ?? [])
    .map((g) => ({ ...g, fields: g.fields.filter((f) => !wanted || f.label.toLowerCase().includes(wanted) || f.field.includes(wanted)) }))
    .filter((g) => g.fields.length > 0);

  return (
    <Sheet className="px-5 pt-4 pb-5">
      <SectionTitle icon="quotes">Quotation code</SectionTitle>
      <p className="text-meta text-ink-3">
        Write the quotation in HTML, with your own styles. Put a field where a detail goes, for example %customer_name%. Between {fields?.loop[0] ?? "%lines_start%"} and{" "}
        {fields?.loop[1] ?? "%lines_end%"}, a table row repeats for each product.
      </p>

      <div className="mt-3 grid gap-4 xl:grid-cols-[15rem_minmax(0,1fr)_minmax(0,1fr)]">
        <div className="min-w-0">
          <p className="mb-1.5 text-sm font-medium text-ink">Fields</p>
          <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Find a field" aria-label="Find a field" />
          <div className="mt-2 max-h-[34rem] space-y-3 overflow-y-auto pr-1">
            {!fields && !problem && <p className="text-meta text-ink-3">Loading the fields…</p>}
            {groups.map((g) => (
              <div key={g.name}>
                <p className="text-meta font-semibold text-ink-2">{g.name}</p>
                <ul className="mt-1 space-y-0.5">
                  {g.fields.map((f) => (
                    <li key={f.field}>
                      <button
                        type="button"
                        onClick={() => insert(f.field)}
                        title={`Put ${f.field} where the cursor is`}
                        className="flex w-full items-baseline justify-between gap-2 rounded-lg px-2 py-1 text-left hover:bg-hema-tint focus-visible:ring-2 focus-visible:ring-hema focus-visible:outline-none"
                      >
                        <span className="truncate text-sm text-ink">{f.label}</span>
                        <code className="shrink-0 text-[11px] text-ink-3">{f.field}</code>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            {fields && groups.length === 0 && <p className="text-meta text-ink-3">No field is called that.</p>}
          </div>
        </div>

        <div className="min-w-0">
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <label htmlFor="template-code" className="text-sm font-medium text-ink">
              Code
            </label>
            {fields && !html.trim() && (
              <Button variant="quiet" onClick={() => onChange(fields.starter)}>
                Start from our layout
              </Button>
            )}
          </div>
          <textarea
            id="template-code"
            ref={area}
            value={html}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              // Tab indents here, as in any code editor; Esc then Tab leaves the box.
              if (e.key === "Tab" && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                insert("  ");
              }
            }}
            spellCheck={false}
            autoCapitalize="off"
            autoComplete="off"
            placeholder={"<div>\n  <h1>%heading%</h1>\n  <p>%customer_name%</p>\n  %items_table%\n</div>"}
            className="h-[36rem] w-full resize-y rounded-lg border border-rule-strong bg-bench/40 p-3 font-mono text-[12.5px] leading-relaxed text-ink focus-visible:border-hema focus-visible:ring-2 focus-visible:ring-hema/30 focus-visible:outline-none"
          />
          <p className="mt-1 text-meta text-ink-3">Up to 200,000 characters. Pictures go in as the logo and e-signature, then %logo% and %signature%.</p>
        </div>

        <div className="min-w-0">
          <p className="mb-1.5 flex items-baseline justify-between gap-2 text-sm font-medium text-ink">
            Preview
            <span className="text-meta font-normal text-ink-3">{busy ? "Updating…" : (preview?.using ?? "")}</span>
          </p>
          <iframe
            title="Preview of the quotation"
            sandbox=""
            srcDoc={preview?.html ?? ""}
            className="h-[36rem] w-full rounded-lg border border-rule bg-white"
          />
          {problem && <p className="mt-1 text-meta text-danger">{problem}</p>}
        </div>
      </div>
    </Sheet>
  );
}
