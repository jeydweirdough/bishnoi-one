"use client";

import { useState } from "react";
import { deletePermit } from "@/src/actions/executive";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { PermitModal } from "@/src/components/executive-modals";
import type { ComplianceRecord } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Figure } from "@/src/platform/ui/figure";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

export function PermitsScreen({ permits: initialPermits }: { permits: ComplianceRecord[] }) {
  const [permits, setPermits] = useState<ComplianceRecord[]>(initialPermits);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [modalPermit, setModalPermit] = useState<ComplianceRecord | null | "new">(null);

  const categories = [
    { key: "all", label: "All Permits" },
    { key: "boc", label: "BOC CPRS" },
    { key: "lgu", label: "LGU Mayor's Permit" },
    { key: "sec", label: "SEC GIS" },
    { key: "bir", label: "BIR Registrations" },
    { key: "fda", label: "FDA Licenses" },
    { key: "sanitary_fire", label: "Fire & Sanitary" },
  ];

  const filtered = permits.filter(
    (p) => selectedCategory === "all" || p.category === selectedCategory
  );

  const totalCount = permits.length;
  const overdueCount = permits.filter((p) => (p.daysRemaining ?? 100) < 0).length;
  const urgentCount = permits.filter((p) => {
    const d = p.daysRemaining ?? 100;
    return d >= 0 && d <= 30;
  }).length;

  return (
    <>
      <PageHeader
        title="Registrations & Regulatory Permits"
        crumbs={[{ href: "/", label: "Executive Admin" }, { href: "/permits", label: "Permits" }]}
        actions={
          <Button variant="primary" onClick={() => setModalPermit("new")}>
            <Icon name="permits" className="mr-1.5 size-4" />
            Record Registration / Permit
          </Button>
        }
      >
        Track and renew BOC CPRS accreditations, LGU Mayor's business permits, SEC annual reportorial GIS, BIR Form 0605, and FDA licenses.
      </PageHeader>

      {/* Top Figure KPI Summary Strip */}
      <Sheet className="mb-5 grid divide-y divide-rule sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <Figure label="Total Registrations & Permits" value={totalCount} />
        <Figure label="Overdue for Filing / Renewal" value={overdueCount} flag={overdueCount > 0} />
        <Figure label="Renewals Due within 30 Days" value={urgentCount} flag={urgentCount > 0} />
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
          <Empty title="No registrations or permits in this category" icon="permits">
            Select another category or record a new compliance permit for the company.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {filtered.map((p) => (
              <li
                key={p.id}
                className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 py-3.5 transition-colors hover:bg-bench/40"
              >
                <div className="flex min-w-0 flex-1 items-start gap-3">
                  <div className="mt-0.5 shrink-0">
                    <CountdownBadge daysRemaining={p.daysRemaining} urgencyTier={p.urgencyTier} />
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-semibold text-sm text-ink">{p.title}</span>
                      <span className="text-meta text-ink-2">· {p.agency}</span>
                    </div>

                    <p className="mt-0.5 text-meta text-ink-3">
                      Ref: <span className="font-mono text-ink-2">{p.referenceNumber}</span>
                      {p.responsiblePerson && <> · Lead: <span className="text-ink-2">{p.responsiblePerson}</span></>}
                      {p.notes && <> · <span className="italic">{p.notes}</span></>}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 shrink-0">
                  <div className="text-right">
                    <span className="block text-meta font-medium text-ink tabular-nums">
                      {new Date(p.expirationDate).toLocaleDateString("en-PH", { dateStyle: "medium" })}
                    </span>
                    <span className="inline-flex items-center rounded-[2px] px-1.5 py-0.5 text-stamp uppercase border border-rule text-ink-3">
                      {p.status.replace("_", " ")}
                    </span>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setModalPermit(p)}
                      className="rounded-[3px] border border-rule-strong bg-sheet px-2.5 py-1 text-meta font-medium text-ink hover:border-control"
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
                        setPermits((prev) => prev.filter((item) => item.id !== p.id));
                      }}
                    />
                  </div>
                </div>
              </li>
            ))}
          </ul>
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
