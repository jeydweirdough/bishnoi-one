"use client";

import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { deletePermit } from "@/src/actions/executive";
import { ExportButton, ImportButton } from "@/src/components/sheet-actions";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { PermitModal } from "@/src/components/executive-modals";
import type { ComplianceRecord } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { HealthStrip, healthOf } from "@/src/components/overview-charts";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

/** What this person's role lets them do here; the API checks the same. */
type Can = { create: boolean; edit: boolean; delete: boolean };
const ALL: Can = { create: true, edit: true, delete: true };

export function PermitsScreen({ permits: initialPermits, canImport = false, can = ALL }: { permits: ComplianceRecord[]; canImport?: boolean; can?: Can }) {
  const [permits, setPermits] = useState<ComplianceRecord[]>(initialPermits);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [modalPermit, setModalPermit] = useState<ComplianceRecord | null | "new">(null);

  const categories = [
    { key: "all", label: "All" },
    { key: "boc", label: "BOC CPRS" },
    { key: "lgu", label: "Mayor's permit" },
    { key: "sec", label: "SEC GIS" },
    { key: "bir", label: "BIR" },
    { key: "fda", label: "FDA" },
    { key: "sanitary_fire", label: "Fire and sanitary" },
  ];

  const filtered = permits.filter(
    (p) => selectedCategory === "all" || p.category === selectedCategory
  );

  return (
    <>
      <PageHeader
        title="Permits"
        actions={
          <>
            <ExportButton kind="permits" />
            {canImport && <ImportButton href="/permits/import" />}
            {can.create && (
              <Button variant="primary" onClick={() => setModalPermit("new")}>
                <Icon name="permits" className="mr-1.5 size-4" />
                New permit
              </Button>
            )}
          </>
        }
      >
        Government registrations and permits the company must keep current: BOC, Mayor's permit, SEC, BIR, FDA, fire and sanitary.
      </PageHeader>

      <HealthStrip label="permits" {...healthOf(permits.map((p) => p.daysRemaining), 30)} />

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
          <Empty title="No permits here" icon="permits">
            Choose another category, or add a permit.
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
                      {/* Edit and delete sit with the record they act on. */}
                      <span className="inline-flex items-center">
                        {can.edit && (
                          <button
                            type="button"
                            onClick={() => setModalPermit(p)}
                            aria-label="Edit permit"
                            title="Edit permit"
                            className="inline-flex size-7 items-center justify-center rounded-[3px] text-ink-3 hover:bg-hema-tint hover:text-hema"
                          >
                            <Pencil className="size-3.5" aria-hidden />
                          </button>
                        )}
                        {can.delete && (
                          <ConfirmButton
                            label={<span className="sr-only">Delete permit</span>}
                            icon={<Trash2 className="size-3.5" aria-hidden />}
                            triggerTitle="Delete permit"
                            triggerClassName="!size-7 !px-0 !text-ink-3 hover:!bg-danger/10 hover:!text-danger"
                                                  title={`Delete ${p.title}?`}
                            body="This permit and its renewal alerts are deleted. This cannot be undone."
                            confirmLabel="Delete permit"
                            danger
                            triggerVariant="quiet"
                            triggerSize="sm"
                            onConfirm={async () => {
                            await deletePermit(p.id);
                            setPermits((prev) => prev.filter((item) => item.id !== p.id));
                            }}
                            
                          />
                        )}
                      </span>
                      <span className="text-meta text-ink-2">· {p.agency}</span>
                    </div>

                    <p className="mt-0.5 text-meta text-ink-3">
                      Ref: <span className="font-mono text-ink-2">{p.referenceNumber}</span>
                      {p.responsiblePerson && <> · Responsible: <span className="text-ink-2">{p.responsiblePerson}</span></>}
                      {p.notes && <> · <span className="text-ink-3">{p.notes}</span></>}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 shrink-0">
                  <div className="text-right">
                    <span className="block text-meta font-medium text-ink tabular-nums">
                      {new Date(p.expirationDate).toLocaleDateString("en-PH", { dateStyle: "medium" })}
                    </span>
                    <span className="inline-block rounded-[2px] border border-rule px-1.5 py-0.5 text-meta text-ink-3 first-letter:uppercase">
                      {p.status.replace("_", " ")}
                    </span>
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
