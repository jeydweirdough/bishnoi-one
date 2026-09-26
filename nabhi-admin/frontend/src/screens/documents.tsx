"use client";

import { useState } from "react";
import { deleteDocument } from "@/src/actions/executive";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { DocumentModal } from "@/src/components/executive-modals";
import type { CorporateDocument } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

export function DocumentsScreen({ documents: initialDocuments }: { documents: CorporateDocument[] }) {
  const [documents, setDocuments] = useState<CorporateDocument[]>(initialDocuments);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [modalDocument, setModalDocument] = useState<CorporateDocument | null | "new">(null);

  const categories = [
    { key: "all", label: "All Documents" },
    { key: "insurance", label: "Corporate Insurance (D&O, CGL)" },
    { key: "commercial_contract", label: "Commercial Agreements" },
    { key: "nda", label: "NDAs" },
    { key: "board_resolution", label: "Board Resolutions" },
    { key: "legal_retainer", label: "Legal Retainers" },
  ];

  const filtered = initialDocuments.filter(
    (d) => selectedCategory === "all" || d.category === selectedCategory
  );

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

      {/* Category Tabs */}
      <div className="mb-4 flex flex-wrap items-center gap-1.5 border-b border-rule pb-2">
        {categories.map((cat) => (
          <button
            key={cat.key}
            type="button"
            onClick={() => setSelectedCategory(cat.key)}
            className={`rounded-[2px] px-3 py-1 text-meta font-medium transition-colors ${
              selectedCategory === cat.key
                ? "bg-hema text-white"
                : "text-ink-2 hover:bg-bench hover:text-ink"
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      <Sheet className="overflow-hidden">
        {filtered.length === 0 ? (
          <Empty title="No documents found in this category" icon="documents">
            Record corporate insurance policies, vendor master agreements, or board resolutions.
          </Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-rule bg-bench/60 text-caps text-ink-3 uppercase">
                <tr>
                  <th className="px-4 py-3 font-semibold">Document / Policy Title</th>
                  <th className="px-4 py-3 font-semibold">Counterparty / Underwriter</th>
                  <th className="px-4 py-3 font-semibold">Policy / Ref #</th>
                  <th className="px-4 py-3 font-semibold">Expiration & Notice Deadline</th>
                  <th className="px-4 py-3 font-semibold">Annual Value</th>
                  <th className="px-4 py-3 font-semibold">Custodian</th>
                  <th className="px-4 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {filtered.map((d) => (
                  <tr key={d.id} className="transition-colors hover:bg-bench/20">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-ink">{d.title}</div>
                      <div className="flex items-center gap-2 text-meta text-ink-3">
                        <span className="capitalize">{d.category.replace("_", " ")}</span>
                        {d.autoRenews && (
                          <span className="inline-flex items-center rounded-[2px] bg-hema-tint px-1 text-stamp font-semibold text-hema uppercase">
                            Auto-renews ({d.noticePeriodDays}d notice)
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-ink-2">{d.counterparty}</td>
                    <td className="px-4 py-3 font-mono text-meta text-ink-2">{d.referenceNumber || "—"}</td>
                    <td className="px-4 py-3">
                      {d.expirationDate ? (
                        <div className="flex items-center gap-2">
                          <CountdownBadge daysRemaining={d.daysRemaining} urgencyTier={d.urgencyTier} />
                          <span className="text-meta text-ink-3">
                            {new Date(d.expirationDate).toLocaleDateString("en-PH", { dateStyle: "medium" })}
                          </span>
                        </div>
                      ) : (
                        <span className="text-meta text-ink-3">Ongoing / No Expiry</span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-medium text-ink">
                      {d.annualValue
                        ? `PHP ${d.annualValue.toLocaleString("en-PH", { minimumFractionDigits: 2 })}`
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-meta text-ink-2">{d.custodian || "Executive Office"}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => setModalDocument(d)}
                          className="rounded-[2px] px-2 py-1 text-meta font-medium text-hema hover:bg-hema-tint"
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
                          }}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
