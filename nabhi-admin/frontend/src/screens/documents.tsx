"use client";

import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { deleteDocument } from "@/src/actions/executive";
import { ExportButton, ImportButton } from "@/src/components/sheet-actions";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { DocumentModal } from "@/src/components/executive-modals";
import type { CorporateDocument } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { HealthStrip, healthOf } from "@/src/components/overview-charts";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

export function DocumentsScreen({ documents: initialDocuments, canImport = false }: { documents: CorporateDocument[]; canImport?: boolean }) {
  const [documents, setDocuments] = useState<CorporateDocument[]>(initialDocuments);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [modalDocument, setModalDocument] = useState<CorporateDocument | null | "new">(null);

  const categories = [
    { key: "all", label: "All" },
    { key: "insurance", label: "Insurance" },
    { key: "commercial_contract", label: "Contracts" },
    { key: "nda", label: "NDAs" },
    { key: "board_resolution", label: "Board resolutions" },
    { key: "legal_retainer", label: "Legal retainers" },
  ];

  const filtered = documents.filter(
    (d) => selectedCategory === "all" || d.category === selectedCategory
  );

  return (
    <>
      <PageHeader
        title="Documents"
        actions={
          <>
            <ExportButton kind="documents" />
            {canImport && <ImportButton href="/documents/import" />}
            <Button variant="primary" onClick={() => setModalDocument("new")}>
              <Icon name="documents" className="mr-1.5 size-4" />
              New document
            </Button>
          </>
        }
      >
        Insurance policies, contracts, NDAs, board resolutions and legal retainers, with their renewal and cancellation dates.
      </PageHeader>

      <HealthStrip label="documents with an expiry date" {...healthOf(documents.map((d) => d.daysRemaining), 60)} />

      {/* Filter Tabs */}
      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        <div className="inline-flex flex-wrap rounded-[3px] border border-rule-strong bg-sheet p-0.5">
          {categories.map((cat) => (
            <button
              key={cat.key}
              type="button"
              onClick={() => setSelectedCategory(cat.key)}
              className={`rounded-[2px] px-3 py-1 text-meta transition-colors ${
                selectedCategory === cat.key
                  ? "bg-hema-tint font-semibold text-hema"
                  : "text-ink-2 hover:text-ink"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      <Sheet>
        {filtered.length === 0 ? (
          <Empty title="No documents here" icon="documents">
            Choose another category, or add a document.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {filtered.map((d) => (
              <li
                key={d.id}
                className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 py-3.5 transition-colors hover:bg-bench/40"
              >
                <div className="flex min-w-0 flex-1 items-start gap-3">
                  <div className="mt-0.5 shrink-0">
                    {d.expirationDate ? (
                      <CountdownBadge daysRemaining={d.daysRemaining} urgencyTier={d.urgencyTier} />
                    ) : (
                      <span className="inline-flex items-center rounded-[2px] border border-rule px-1.5 py-0.5 text-meta font-medium text-ink-3">
                        Active
                      </span>
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-semibold text-sm text-ink">{d.title}</span>
                      {/* Edit and delete sit with the record they act on. */}
                      <span className="inline-flex items-center">
                        <button
                          type="button"
                          onClick={() => setModalDocument(d)}
                          aria-label="Edit document"
                          title="Edit document"
                          className="inline-flex size-7 items-center justify-center rounded-[3px] text-ink-3 hover:bg-hema-tint hover:text-hema"
                        >
                          <Pencil className="size-3.5" aria-hidden />
                        </button>
                        <ConfirmButton
                          label={<span className="sr-only">Delete document</span>}
                          icon={<Trash2 className="size-3.5" aria-hidden />}
                          triggerTitle="Delete document"
                          triggerClassName="!size-7 !px-0 !text-ink-3 hover:!bg-danger/10 hover:!text-danger"
                                                title={`Delete ${d.title}?`}
                          body="This document and its renewal alerts are deleted. This cannot be undone."
                          confirmLabel="Delete document"
                          danger
                          triggerVariant="quiet"
                          triggerSize="sm"
                          onConfirm={async () => {
                          await deleteDocument(d.id);
                          setDocuments((prev) => prev.filter((item) => item.id !== d.id));
                          }}
                          
                        />
                      </span>
                      <span className="text-meta text-ink-2">· {d.counterparty}</span>
                      {d.autoRenews && (
                        <span className="rounded-[2px] bg-hema-tint px-1.5 py-0.2 text-meta font-semibold text-hema">
                          Auto-renews ({d.noticePeriodDays}d notice)
                        </span>
                      )}
                    </div>

                    <p className="mt-0.5 text-meta text-ink-3">
                      Category: <span className="capitalize text-ink-2">{d.category.replace("_", " ")}</span>
                      {d.referenceNumber && <> · Ref: <span className="font-mono text-ink-2">{d.referenceNumber}</span></>}
                      {d.annualValue ? <> · Value: <span className="font-medium text-ink tabular-nums">PHP {d.annualValue.toLocaleString("en-PH", { minimumFractionDigits: 2 })}</span></> : null}
                      {d.custodian && <> · Custodian: <span className="text-ink-2">{d.custodian}</span></>}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 shrink-0">
                  <div className="text-right">
                    <span className="block text-meta font-medium text-ink tabular-nums">
                      {d.expirationDate
                        ? new Date(d.expirationDate).toLocaleDateString("en-PH", { dateStyle: "medium" })
                        : "Ongoing"}
                    </span>
                    <span className="inline-block rounded-[2px] border border-rule px-1.5 py-0.5 text-meta text-ink-3 first-letter:uppercase">
                      {d.status.replace("_", " ")}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Sheet>

      {modalDocument !== null && (
        <DocumentModal
          document={modalDocument === "new" ? null : modalDocument}
          onClose={() => setModalDocument(null)}
        />
      )}
    </>
  );
}
