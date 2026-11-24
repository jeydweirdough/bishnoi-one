"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/modules/finance/platform/ui/field";
import { screen } from "@/src/modules/finance/lib/links";
import { convertScanToBill, deleteDocumentScan, uploadDocumentScan } from "./actions";
import type { DocumentScanItem } from "./types";

type SupplierOption = { id: string; name: string; tin: string | null };
type AccountOption = { id: string; code: string; name: string };

const MAX_BYTES = 4 * 1024 * 1024;

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const s = String(reader.result ?? "");
      resolve(s.includes(",") ? s.split(",")[1] : s);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function runBrowserOcr(file: File, onProgress: (pct: number) => void): Promise<string> {
  const { createWorker } = await import("tesseract.js");
  const worker = await createWorker("eng", 1, {
    logger: (m) => {
      if (m.status === "recognizing text" && typeof m.progress === "number") {
        onProgress(Math.round(m.progress * 100));
      }
    },
  });
  try {
    const {
      data: { text },
    } = await worker.recognize(file);
    return text ?? "";
  } finally {
    await worker.terminate();
  }
}

function ConfidencePill({ level }: { level?: string }) {
  const label = level === "high" ? "High confidence" : level === "medium" ? "Check value" : "Needs review";
  return <span className="ml-2 rounded bg-bench px-1.5 py-0.5 text-[11px] font-medium text-ink-2">{label}</span>;
}

export function ScanClient({
  today,
  items,
  suppliers,
  accounts,
  vatKinds,
  canCreate,
}: {
  today: string;
  items: DocumentScanItem[];
  suppliers: SupplierOption[];
  accounts: AccountOption[];
  vatKinds: { key: string; label: string }[];
  canCreate: boolean;
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [ocrStatus, setOcrStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(items[0]?.id ?? null);

  const selected = items.find((x) => x.id === selectedId) ?? items[0] ?? null;

  const [supplierId, setSupplierId] = useState(selected?.parsed?.supplierId ?? suppliers[0]?.id ?? "");
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? "");
  const [billNumber, setBillNumber] = useState(selected?.parsed?.billNumber ?? "");
  const [billDate, setBillDate] = useState(selected?.parsed?.billDate ?? today);
  const [amountPesos, setAmountPesos] = useState(
    selected?.parsed?.totalCentavos ? (selected.parsed.totalCentavos / 100).toFixed(2) : ""
  );
  const [vat, setVat] = useState<string>(selected?.parsed?.vat ?? "vat");
  const [description, setDescription] = useState("");

  function selectScan(scan: DocumentScanItem) {
    setSelectedId(scan.id);
    setError(null);
    setSupplierId(scan.parsed?.supplierId ?? suppliers[0]?.id ?? "");
    setBillNumber(scan.parsed?.billNumber ?? "");
    setBillDate(scan.parsed?.billDate ?? today);
    setAmountPesos(scan.parsed?.totalCentavos ? (scan.parsed.totalCentavos / 100).toFixed(2) : "");
    setVat(scan.parsed?.vat ?? "vat");
    setDescription("");
  }

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError(null);
    if (file.size > MAX_BYTES) {
      setError("Please upload a photo or PDF under 4 MB.");
      return;
    }
    const isPdf = file.type === "application/pdf";
    const isImage = file.type === "image/jpeg" || file.type === "image/png";
    if (!isPdf && !isImage) {
      setError("Upload a JPG, PNG, or PDF supplier invoice.");
      return;
    }
    try {
      let ocrText: string | null = null;
      if (isImage) {
        setOcrStatus("Scanning image in your browser (0%)…");
        ocrText = await runBrowserOcr(file, (pct) => setOcrStatus(`Scanning image in your browser (${pct}%)…`));
      } else {
        setOcrStatus("Extracting text from PDF…");
      }
      const data = await fileToBase64(file);
      setOcrStatus(null);
      start(async () => {
        const res = await uploadDocumentScan({ name: file.name, contentType: file.type, data, ocrText });
        if (!res.ok) return setError(res.error);
        toast.success("Document scanned into inbox");
        selectScan(res.data);
      });
    } catch (err) {
      setOcrStatus(null);
      setError(err instanceof Error ? err.message : "Could not read that file.");
    }
  }

  function onConvert(e: React.FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setError(null);
    const amountCentavos = Math.round(Number(amountPesos) * 100);
    if (!supplierId || !accountId || !billNumber.trim() || !Number.isFinite(amountCentavos) || amountCentavos <= 0) {
      setError("Confirm the supplier, expense account, invoice number, and positive amount.");
      return;
    }
    start(async () => {
      const res = await convertScanToBill(selected.id, {
        supplierId,
        accountId,
        billNumber: billNumber.trim(),
        billDate,
        amountCentavos,
        vat,
        description: description.trim() || undefined,
        amountsIncludeVat: true,
      });
      if (!res.ok) return setError(res.error);
      toast.success(`Draft bill #${res.data.billNo} created with attachment`);
      router.push(screen(res.data.href));
    });
  }

  return (
    <div className="space-y-6">
      {canCreate && (
        <div className="rounded-lg border border-rule bg-sheet p-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-ink">Upload supplier invoice or receipt</h2>
            <p className="text-meta text-ink-2">
              Photos (JPG/PNG) are read locally in your browser using Tesseract OCR; PDFs are parsed on the server. Printer ATP TIN stamps are ignored automatically.
            </p>
            {ocrStatus && <p className="mt-1 text-meta font-medium text-ink">{ocrStatus}</p>}
          </div>
          <label className="inline-flex cursor-pointer items-center rounded-lg border border-control bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90">
            <span>{ocrStatus ? "Reading…" : "Choose JPG / PNG / PDF"}</span>
            <input type="file" accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf" className="hidden" onChange={onPickFile} disabled={Boolean(ocrStatus) || pending} />
          </label>
        </div>
      )}

      <FormError message={error} />

      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-5 space-y-4">
          <div className="rounded-lg border border-rule bg-sheet divide-y divide-rule">
            <div className="px-4 py-2.5 text-meta font-semibold text-ink-2 bg-bench">Scan queue ({items.length})</div>
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => selectScan(item)}
                className={`w-full px-4 py-3 text-left transition-colors ${selected?.id === item.id ? "bg-bench" : "hover:bg-bench/60"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium text-ink">{item.fileName}</span>
                  <span className="shrink-0 rounded bg-sheet px-2 py-0.5 text-meta text-ink-2 border border-rule">
                    {item.linkedBillId ? "Linked to bill" : "Ready"}
                  </span>
                </div>
                <div className="mt-1 text-meta text-ink-3">
                  {item.parsed?.supplierName ?? "Supplier unverified"}
                  {item.parsed?.billNumber ? ` · #${item.parsed.billNumber}` : ""}
                  {item.parsed?.totalCentavos ? ` · PHP ${(item.parsed.totalCentavos / 100).toLocaleString("en-PH", { minimumFractionDigits: 2 })}` : ""}
                </div>
              </button>
            ))}
            {items.length === 0 && <div className="px-4 py-8 text-center text-sm text-ink-3">No scanned receipts yet.</div>}
          </div>

          {selected && (
            <div className="rounded-lg border border-rule bg-sheet overflow-hidden">
              <div className="flex items-center justify-between border-b border-rule bg-bench px-4 py-2 text-meta font-medium text-ink-2">
                <span className="truncate">Preview: {selected.fileName}</span>
                <a
                  href={`/finance/scans/file?id=${encodeURIComponent(selected.id)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 text-ink underline hover:text-ink-2"
                >
                  Open file
                </a>
              </div>
              {selected.contentType === "application/pdf" ? (
                <div className="p-4 space-y-3 bg-bench/50">
                  <div className="flex items-center justify-between rounded border border-rule bg-sheet px-3 py-2 text-meta">
                    <span className="font-medium text-ink">PDF document ({Math.max(1, Math.round(selected.size / 1024))} KB)</span>
                    <a
                      href={`/finance/scans/file?id=${encodeURIComponent(selected.id)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded border border-control bg-sheet px-2.5 py-1 font-medium text-ink hover:border-ink"
                    >
                      Open PDF in new tab
                    </a>
                  </div>
                  <div className="rounded border border-rule bg-sheet p-3">
                    <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-3">Extracted PDF text</div>
                    <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs text-ink-2">
                      {selected.rawText || "No embedded text found in this PDF. Enter details manually on the right."}
                    </pre>
                  </div>
                </div>
              ) : (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={`/finance/scans/file?id=${encodeURIComponent(selected.id)}`}
                  alt={selected.fileName}
                  className="max-h-96 w-full object-contain bg-bench"
                />
              )}
            </div>
          )}
        </div>

        <div className="lg:col-span-7">
          {selected ? (
            <form onSubmit={onConvert} className="rounded-lg border border-rule bg-sheet p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-semibold text-ink">
                  {selected.linkedBillId ? "Converted to draft bill" : "Verify & create draft bill"}
                </h3>
                {canCreate && !selected.linkedBillId && (
                  <Button
                    type="button"
                    size="sm"
                    onClick={() =>
                      start(async () => {
                        const r = await deleteDocumentScan(selected.id);
                        if (!r.ok) toast.error(r.error);
                        else {
                          toast.success("Scan removed");
                          setSelectedId(null);
                        }
                      })
                    }
                  >
                    Remove scan
                  </Button>
                )}
              </div>

              {selected.linkedBillId ? (
                <div className="rounded border border-rule bg-bench p-4 text-sm text-ink">
                  This document is already attached to a draft bill.{" "}
                  <Link href={screen(`/bills/${selected.linkedBillId}`)} className="font-semibold underline">
                    Open draft bill
                  </Link>
                </div>
              ) : (
                <>
                  {selected.parsed?.warnings && selected.parsed.warnings.length > 0 && (
                    <div className="rounded border border-rule bg-bench px-3 py-2 text-meta text-ink-2 space-y-0.5">
                      {selected.parsed.warnings.map((w) => (
                        <div key={w}>• {w}</div>
                      ))}
                    </div>
                  )}
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field
                      label={
                        <span>
                          Supplier <ConfidencePill level={selected.parsed?.confidence} />
                        </span>
                      }
                    >
                      {(p) => (
                        <Select {...p} value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
                          <option value="">Pick supplier…</option>
                          {suppliers.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.name}
                              {s.tin ? ` (${s.tin})` : ""}
                            </option>
                          ))}
                        </Select>
                      )}
                    </Field>
                    <Field label="Expense / Asset account">
                      {(p) => (
                        <Select {...p} value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                          {accounts.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.code} · {a.name}
                            </option>
                          ))}
                        </Select>
                      )}
                    </Field>
                    <Field label="Supplier invoice / SI #">
                      {(p) => <Input {...p} value={billNumber} onChange={(e) => setBillNumber(e.target.value)} placeholder="e.g. SI-001234" />}
                    </Field>
                    <Field label="Bill date">
                      {(p) => <Input {...p} type="date" value={billDate} onChange={(e) => setBillDate(e.target.value)} />}
                    </Field>
                    <Field label="Total amount (PHP, VAT-incl.)">
                      {(p) => <Input {...p} type="number" step="0.01" min="0.01" value={amountPesos} onChange={(e) => setAmountPesos(e.target.value)} />}
                    </Field>
                    <Field label="VAT treatment">
                      {(p) => (
                        <Select {...p} value={vat} onChange={(e) => setVat(e.target.value)}>
                          {vatKinds.map((v) => (
                            <option key={v.key} value={v.key}>
                              {v.label}
                            </option>
                          ))}
                        </Select>
                      )}
                    </Field>
                  </div>
                  <Field label="Description" optional>
                    {(p) => <Input {...p} value={description} onChange={(e) => setDescription(e.target.value)} placeholder={`From ${selected.fileName}`} />}
                  </Field>
                  <Button type="submit" variant="primary" loading={pending}>
                    Create draft bill with attachment
                  </Button>
                </>
              )}

              {selected.rawText && (
                <details className="pt-2">
                  <summary className="cursor-pointer text-meta text-ink-3 hover:text-ink">Show extracted text</summary>
                  <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded border border-rule bg-bench p-3 text-xs text-ink-2">
                    {selected.rawText}
                  </pre>
                </details>
              )}
            </form>
          ) : (
            <div className="rounded-lg border border-rule bg-sheet p-8 text-center text-sm text-ink-3">
              Upload or select a receipt to verify its fields and create a draft bill.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
