"use client";

import { useState } from "react";
import { deleteDocument } from "@/src/actions/executive";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { DocumentModal } from "@/src/components/executive-modals";
import type { CorporateDocument } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Figure } from "@/src/platform/ui/figure";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

export function DocumentsScreen({ documents: initialDocuments }: { documents: CorporateDocument[] }) {
  const [documents, setDocuments] = useState<CorporateDocument[]>(initialDocuments);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [modalDocument, setModalDocument] = useState<CorporateDocument | null | "new">(null);

  const categories = [
    { key: "all", label: "All Documents" },
    { key: "insurance", label: "Insurance (D&O, CGL)" },
    { key: "commercial_contract", label: "Commercial Contracts" },
    { key: "nda", label: "NDAs" },
    { key: "board_resolution", label: "Board Resolutions" },
    { key: "legal_retainer", label: "Legal Retainers" },
  ];

  const filtered = documents.filter(
    (d) => selectedCategory === "all" || d.category === selectedCategory
  );

  const totalCount = documents.length;
  const insuranceCount = documents.filter((d) => d.category === "insurance").length;
  const autoRenewCount = documents.filter((d) => d.autoRenews).length;

  return (
    <>
      <PageHeader
        title="Corporate Documents, Contracts & Insurances"
        crumbs={[{ href: "/", label: "Executive Admin" }, { href: "/documents", label: "Documents" }]}
        actions={
          <Button variant="primary" onClick={() => setModalDocument("new")}>
            <Icon name="documents" className="mr-1.5 size-4" />
            Record Document / Policy
          </Button>
        }
      >
        Directors & Officers (D&O) liability, comprehensive general liability, commercial warehousing contracts, auto-renewal clauses & cancellation deadlines.
      </PageHeader>

      {/* Top Figure KPI Metrics Strip */}
      <Sheet className="mb-5 grid divide-y divide-rule sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <Figure label="Total Corporate Documents" value={totalCount} />
        <Figure label="Corporate Insurance Policies" value={insuranceCount} />
        <Figure label="Auto-Renewing Contracts" value={autoRenewCount} />
      </Sheet>

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
          <Empty title="No documents found in this category" icon="documents">
            Record corporate insurance policies, vendor master agreements, or board resolutions.
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
                      <span className="inline-flex items-center rounded-[2px] border border-rule px-1.5 py-0.5 text-stamp font-medium text-ink-3 uppercase">
                        Active
                      </span>
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-semibold text-sm text-ink">{d.title}</span>
                      <span className="text-meta text-ink-2">· {d.counterparty}</span>
                      {d.autoRenews && (
                        <span className="rounded-[2px] bg-hema-tint px-1.5 py-0.2 text-stamp font-semibold text-hema uppercase">
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
                    <span className="inline-flex items-center rounded-[2px] px-1.5 py-0.5 text-stamp uppercase border border-rule text-ink-3">
                      {d.status.replace("_", " ")}
                    </span>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setModalDocument(d)}
                      className="rounded-[3px] border border-rule-strong bg-sheet px-2.5 py-1 text-meta font-medium text-ink hover:border-control"
                    >
                      Edit
                    </button>
                    <ConfirmButton
                      label="Delete"
                      title="Delete Document Record?"
                      body={`Are you sure you want to delete ${d.title}?`}
                      confirmLabel="Delete Record"
                      danger
                      triggerVariant="quiet"
                      triggerSize="sm"
                      onConfirm={async () => {
                        await deleteDocument(d.id);
                        setDocuments((prev) => prev.filter((item) => item.id !== d.id));
                      }}
                    />
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
