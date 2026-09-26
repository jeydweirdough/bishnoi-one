"use client";

import { useState } from "react";
import { deletePermit } from "@/src/actions/executive";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { PermitModal } from "@/src/components/executive-modals";
import type { ComplianceRecord } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

export function PermitsScreen({ permits: initialPermits }: { permits: ComplianceRecord[] }) {
  const [permits, setPermits] = useState<ComplianceRecord[]>(initialPermits);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [modalPermit, setModalPermit] = useState<ComplianceRecord | null | "new">(null);

  const categories = [
    { key: "all", label: "All Permits" },
    { key: "boc", label: "Bureau of Customs (BOC)" },
    { key: "lgu", label: "LGU Mayor's Permit" },
    { key: "sec", label: "SEC GIS & Filings" },
    { key: "bir", label: "BIR Form 0605 / 2303" },
    { key: "fda", label: "FDA License to Operate" },
    { key: "sanitary_fire", label: "Fire & Sanitary" },
  ];

  const filtered = initialPermits.filter(
    (p) => selectedCategory === "all" || p.category === selectedCategory
  );

  return (
    <>
      <PageHeader
        title="Corporate Registrations & Regulatory Permits"
        crumbs={[{ href: "/", label: "Executive Admin" }, { href: "/permits", label: "Permits" }]}
        actions={
          <Button variant="primary" onClick={() => setModalPermit("new")}>
            <Icon name="permits" className="mr-1.5 size-4" />
            Record Registration / Permit
          </Button>
        }
      >
        Track and renew BOC CPRS accreditations, LGU Mayor's permits, SEC GIS reportorial filings, BIR registrations, and FDA licenses.
      </PageHeader>

      {/* Filter Tabs */}
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
          <Empty title="No permits found in this category" icon="permits">
            Select another category or record a new corporate registration.
          </Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-rule bg-bench/60 text-caps text-ink-3 uppercase">
                <tr>
                  <th className="px-4 py-3 font-semibold">Registration / Permit</th>
                  <th className="px-4 py-3 font-semibold">Regulatory Agency</th>
                  <th className="px-4 py-3 font-semibold">License / Ref #</th>
                  <th className="px-4 py-3 font-semibold">Expiration & Countdown</th>
                  <th className="px-4 py-3 font-semibold">Assigned Lead</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {filtered.map((p) => (
                  <tr key={p.id} className="transition-colors hover:bg-bench/20">
                    <td className="px-4 py-3 font-medium text-ink">
                      <div className="font-semibold text-ink">{p.title}</div>
                      {p.notes && <div className="text-meta text-ink-3 line-clamp-1">{p.notes}</div>}
                    </td>
                    <td className="px-4 py-3 text-ink-2">{p.agency}</td>
                    <td className="px-4 py-3 font-mono text-meta text-ink-2">{p.referenceNumber}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <CountdownBadge daysRemaining={p.daysRemaining} urgencyTier={p.urgencyTier} />
                        <span className="text-meta text-ink-3">
                          {new Date(p.expirationDate).toLocaleDateString("en-PH", { dateStyle: "medium" })}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-meta text-ink-2">{p.responsiblePerson || "—"}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center rounded-[2px] px-1.5 py-0.5 text-stamp uppercase ${
                          p.status === "active"
                            ? "bg-hema-tint text-hema font-semibold"
                            : p.status === "pending_renewal"
                              ? "bg-eosin-tint text-eosin font-semibold"
                              : "border border-rule-strong text-ink-3"
                        }`}
                      >
                        {p.status.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => setModalPermit(p)}
                          className="rounded-[2px] px-2 py-1 text-meta font-medium text-hema hover:bg-hema-tint"
                        >
                          Edit
                        </button>
                        <ConfirmButton
                          label="Delete"
                          title="Delete Permit Record?"
                          body={`Are you sure you want to delete ${p.title}? This action cannot be undone.`}
                          confirmLabel="Delete Permit"
                          danger
                          triggerVariant="quiet"
                          triggerSize="sm"
                          onConfirm={async () => {
                            await deletePermit(p.id);
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

      {modalPermit !== null && (
        <PermitModal
          permit={modalPermit === "new" ? null : modalPermit}
          onClose={() => setModalPermit(null)}
        />
      )}
    </>
  );
}
