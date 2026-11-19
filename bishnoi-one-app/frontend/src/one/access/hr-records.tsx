"use client";

import { ExternalLink, Plus, Upload, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useId, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, Input } from "@/src/platform/ui/field";
import { FileDrop, size } from "@/src/platform/ui/file-drop";
import { Pill } from "@/src/platform/ui/figures";
import { Empty } from "@/src/platform/ui/sheet";
import { addHrDocument, removeHrDocument, saveHrDetails } from "./actions";
import type { HrDocument, HrRecords } from "./types";

// An employee's HR records (2026-11-18, step 4I): labelled details (SSS no., TIN, anything HR adds) and documents
// (contracts, clearances, background checks). Only HR and the company's administrators see this; the employee doesn't.

const MAX_BYTES = 10_000_000;
const DAY = 24 * 60 * 60 * 1000;

/** Days until it expires (negative: past), counted in whole days from today. */
function daysLeft(on: string): number {
  const today = new Date();
  const start = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  const [y, m, d] = on.split("-").map(Number);
  return Math.round((Date.UTC(y!, m! - 1, d!) - start) / DAY);
}

function ExpiryMark({ on }: { on: string | null }) {
  if (!on) return null;
  const left = daysLeft(on);
  const date = new Date(`${on}T00:00:00`).toLocaleDateString("en-PH", { day: "numeric", month: "short", year: "numeric" });
  if (left < 0) return <Pill tone="bad">Expired {date}</Pill>;
  if (left <= 30) return <Pill tone="warn">{left === 0 ? "Expires today" : `Expires in ${left} day${left === 1 ? "" : "s"}`}</Pill>;
  return <span className="text-meta text-ink-3">Valid until {date}</span>;
}

export function HrRecordsView({ personId, name, records }: { personId: string; name: string; records: HrRecords }) {
  return (
    <div className="space-y-8">
      <p className="text-meta text-ink-3">Only HR and your company&apos;s administrators see these. {name} doesn&apos;t see them, and every change and every document opened is in the activity log.</p>
      <Details key={JSON.stringify(records.details)} personId={personId} records={records} />
      <Documents personId={personId} name={name} records={records} />
    </div>
  );
}

type Row = { key: number; label: string; value: string };

function Details({ personId, records }: { personId: string; records: HrRecords }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [next, setNext] = useState(records.details.length);
  const [rows, setRows] = useState<Row[]>(records.details.map((d, i) => ({ key: i, ...d })));
  const saved = JSON.stringify(records.details);
  const dirty = JSON.stringify(rows.filter((r) => r.label.trim() || r.value.trim()).map(({ label, value }) => ({ label: label.trim(), value: value.trim() }))) !== saved;
  const used = new Set(rows.map((r) => r.label.trim().toLowerCase()));
  const quick = records.suggestedDetails.filter((l) => !used.has(l.toLowerCase()));

  const add = (label = "") => {
    setRows((rs) => [...rs, { key: next, label, value: "" }]);
    setNext((n) => n + 1);
  };
  const change = (key: number, part: "label" | "value", text: string) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, [part]: text } : r)));

  function save() {
    start(async () => {
      const r = await saveHrDetails(personId, rows.map(({ label, value }) => ({ label, value })));
      if (!r.ok) toast.error(r.error ?? "That didn't work.");
      else {
        toast.success("Details saved.");
        router.refresh();
      }
    });
  }

  return (
    <section aria-labelledby={`hr-details-${personId}`}>
      <h3 id={`hr-details-${personId}`} className="mb-2 text-sm font-semibold text-ink">
        Details
      </h3>
      {rows.length === 0 ? (
        <p className="mb-3 text-sm text-ink-3">No details yet. Add one below.</p>
      ) : (
        <ul className="mb-3 space-y-2">
          {rows.map((r) => (
            <li key={r.key} className="flex items-center gap-2">
              <Input aria-label="Label" placeholder="Label" maxLength={60} value={r.label} onChange={(e) => change(r.key, "label", e.target.value)} className="!w-48 shrink-0" />
              <Input aria-label={r.label || "Value"} placeholder="Value" maxLength={500} value={r.value} onChange={(e) => change(r.key, "value", e.target.value)} />
              <button
                type="button"
                onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))}
                aria-label={`Remove ${r.label || "this detail"}`}
                title="Remove"
                className="grid size-9 shrink-0 place-items-center rounded-lg text-ink-3 hover:bg-bench hover:text-danger"
              >
                <X className="size-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap items-center gap-2">
        {quick.map((l) => (
          <button key={l} type="button" onClick={() => add(l)} className="inline-flex items-center gap-1 rounded-full border border-rule px-2.5 py-1 text-meta text-ink-2 hover:border-ink hover:text-ink">
            <Plus className="size-3" aria-hidden />
            {l}
          </button>
        ))}
        <Button size="sm" icon={<Plus className="size-4" aria-hidden />} onClick={() => add()}>
          Add field
        </Button>
        <Button size="sm" variant="primary" disabled={!dirty || busy} onClick={save}>
          Save details
        </Button>
      </div>
    </section>
  );
}

function Documents({ personId, name, records }: { personId: string; name: string; records: HrRecords }) {
  const router = useRouter();
  const listId = useId();
  const [busy, start] = useTransition();
  const [file, setFile] = useState<File | null>(null);
  const [label, setLabel] = useState("");
  const [expires, setExpires] = useState("");
  const [round, setRound] = useState(0);

  function upload() {
    if (!file || !label.trim()) return;
    const form = new FormData();
    form.set("file", file);
    form.set("label", label.trim());
    form.set("expiresOn", expires);
    start(async () => {
      const r = await addHrDocument(personId, form);
      if (!r.ok) toast.error(r.error ?? "That didn't work.");
      else {
        toast.success(`${label.trim()} added.`);
        setFile(null);
        setLabel("");
        setExpires("");
        setRound((n) => n + 1);
        router.refresh();
      }
    });
  }

  async function remove(d: HrDocument): Promise<boolean> {
    const r = await removeHrDocument(personId, d.id);
    if (!r.ok) {
      toast.error(r.error ?? "That didn't work.");
      return false;
    }
    toast.success(`${d.label} removed.`);
    router.refresh();
    return true;
  }

  return (
    <section aria-labelledby={`hr-documents-${personId}`}>
      <h3 id={`hr-documents-${personId}`} className="mb-2 text-sm font-semibold text-ink">
        Documents
      </h3>
      {records.documents.length === 0 ? (
        <Empty icon="documents" title="No documents yet" compact>
          Add a contract, a clearance or a background check below.
        </Empty>
      ) : (
        <ul className="mb-4 divide-y divide-rule">
          {records.documents.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
                  <span className="truncate">{d.label}</span>
                  <ExpiryMark on={d.expiresOn} />
                </p>
                <p className="truncate text-meta text-ink-3">
                  {d.fileName} · {size(d.size)} · added by {d.uploadedBy}
                </p>
              </div>
              <a
                href={`/platform/hr/${encodeURIComponent(personId)}/documents/${encodeURIComponent(d.id)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-sm font-medium text-sage-deep hover:underline"
              >
                Open
                <ExternalLink className="size-3.5" aria-hidden />
              </a>
              <ConfirmButton
                label={<X className="size-3.5" aria-hidden />}
                triggerVariant="quiet"
                triggerSize="sm"
                triggerTitle={`Remove ${d.label}`}
                title={`Remove ${d.label}`}
                body={`${d.fileName} is removed from ${name}'s HR records for good.`}
                confirmLabel="Remove"
                onConfirm={() => remove(d)}
              />
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 grid gap-3 rounded-lg border border-rule p-4">
        <FileDrop key={round} accept=".pdf,.png,.jpg,.jpeg,.docx" note="PDF, PNG, JPEG or Word (.docx), up to 10 MB" maxBytes={MAX_BYTES} onFile={setFile} busy={busy} />
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="What it is">
            {(f) => (
              <>
                <Input {...f} list={listId} placeholder="For example Contract" maxLength={60} value={label} onChange={(e) => setLabel(e.target.value)} />
                <datalist id={listId}>
                  {records.suggestedDocuments.map((l) => (
                    <option key={l} value={l} />
                  ))}
                </datalist>
              </>
            )}
          </Field>
          <Field label="Expires on" optional>
            {(f) => <Input {...f} type="date" value={expires} onChange={(e) => setExpires(e.target.value)} />}
          </Field>
        </div>
        <div>
          <Button variant="primary" icon={<Upload className="size-4" aria-hidden />} disabled={!file || !label.trim() || busy} onClick={upload}>
            Add document
          </Button>
        </div>
      </div>
    </section>
  );
}
