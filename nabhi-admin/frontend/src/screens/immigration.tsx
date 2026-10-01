"use client";

import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { deleteImmigration } from "@/src/actions/executive";
import { ExportButton, ImportButton } from "@/src/components/sheet-actions";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { ImmigrationModal } from "@/src/components/executive-modals";
import type { ImmigrationRecord } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { HealthStrip, healthOf } from "@/src/components/overview-charts";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

/** What this person's role lets them do here; the API checks the same. */
type Can = { create: boolean; edit: boolean; delete: boolean };
const ALL: Can = { create: true, edit: true, delete: true };

export function ImmigrationScreen({ records: initialRecords, canImport = false, can = ALL }: { records: ImmigrationRecord[]; canImport?: boolean; can?: Can }) {
  const [records, setRecords] = useState<ImmigrationRecord[]>(initialRecords);
  const [selectedType, setSelectedType] = useState<string>("all");
  const [modalRecord, setModalRecord] = useState<ImmigrationRecord | null | "new">(null);

  const types = [
    { key: "all", label: "All" },
    { key: "acr_card", label: "ACR I-Card" },
    { key: "aep_permit", label: "DOLE AEP" },
    { key: "visa", label: "9(g) visas" },
    { key: "passport", label: "Passports" },
    { key: "exec_id", label: "Company IDs" },
  ];

  const filtered = records.filter(
    (r) => selectedType === "all" || r.documentType === selectedType
  );

  const docTypeLabel = (type: string) => {
    switch (type) {
      case "acr_card":
        return "ACR I-Card";
      case "aep_permit":
        return "DOLE AEP";
      case "visa":
        return "Executive Visa";
      case "passport":
        return "Passport";
      case "exec_id":
        return "Executive ID";
      default:
        return type.toUpperCase();
    }
  };


  return (
    <>
      <PageHeader
        title="Expatriates"
        actions={
          <>
            <ExportButton kind="expatriates" />
            {canImport && <ImportButton href="/immigration/import" />}
            {can.create && (
              <Button variant="primary" onClick={() => setModalRecord("new")}>
                <Icon name="immigration" className="mr-1.5 size-4" />
                New expatriate document
              </Button>
            )}
          </>
        }
      >
        Foreign employees' ACR I-Cards, DOLE work permits (AEP), 9(g) visas and passports, with their expiry dates.
      </PageHeader>

      <HealthStrip label="expatriate documents" {...healthOf(records.map((r) => r.daysRemaining), 60)} />

      {/* Filter Tabs */}
      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        <div className="inline-flex flex-wrap rounded-[3px] border border-rule-strong bg-sheet p-0.5">
          {types.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setSelectedType(t.key)}
              className={`rounded-[2px] px-3 py-1 text-meta transition-colors ${
                selectedType === t.key
                  ? "bg-hema-tint font-semibold text-hema"
                  : "text-ink-2 hover:text-ink"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <Sheet>
        {filtered.length === 0 ? (
          <Empty title="No documents here" icon="immigration">
            Choose another category, or add an expatriate document.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {filtered.map((r) => (
              <li
                key={r.id}
                className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 py-3.5 transition-colors hover:bg-bench/40"
              >
                <div className="flex min-w-0 flex-1 items-start gap-3">
                  <div className="mt-0.5 shrink-0">
                    <CountdownBadge daysRemaining={r.daysRemaining} urgencyTier={r.urgencyTier} />
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-semibold text-sm text-ink">{r.individualName}</span>
                      {/* Edit and delete sit with the record they act on. */}
                      <span className="inline-flex items-center">
                        {can.edit && (
                          <button
                            type="button"
                            onClick={() => setModalRecord(r)}
                            aria-label="Edit document"
                            title="Edit document"
                            className="inline-flex size-7 items-center justify-center rounded-[3px] text-ink-3 hover:bg-hema-tint hover:text-hema"
                          >
                            <Pencil className="size-3.5" aria-hidden />
                          </button>
                        )}
                        {can.delete && (
                          <ConfirmButton
                            label={<span className="sr-only">Delete document</span>}
                            icon={<Trash2 className="size-3.5" aria-hidden />}
                            triggerTitle="Delete document"
                            triggerClassName="!size-7 !px-0 !text-ink-3 hover:!bg-danger/10 hover:!text-danger"
                                                  title={`Delete ${r.individualName}'s ${docTypeLabel(r.documentType)}?`}
                            body="This document and its renewal alerts are deleted. This cannot be undone."
                            confirmLabel="Delete document"
                            danger
                            triggerVariant="quiet"
                            triggerSize="sm"
                            onConfirm={async () => {
                            await deleteImmigration(r.id);
                            setRecords((prev) => prev.filter((item) => item.id !== r.id));
                            }}
                            
                          />
                        )}
                      </span>
                      <span className="text-meta text-ink-2">· {r.designation}</span>
                      <span className="inline-block rounded-[2px] border border-rule px-1.5 py-0.2 text-meta font-medium text-ink-3 first-letter:uppercase">
                        {r.nationality}
                      </span>
                    </div>

                    <p className="mt-0.5 text-meta text-ink-3">
                      <span className="font-semibold text-ink-2">{docTypeLabel(r.documentType)}</span>:{" "}
                      <span className="font-mono text-ink-2">{r.documentNumber}</span>
                      {r.sponsoringEntity && <> · Sponsor: <span className="text-ink-2">{r.sponsoringEntity}</span></>}
                      {r.assignedAssistant && <> · Assistant: <span className="text-ink-2">{r.assignedAssistant}</span></>}
                      {r.notes && <> · <span className="text-ink-3">{r.notes}</span></>}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 shrink-0">
                  <div className="text-right">
                    <span className="block text-meta font-medium text-ink tabular-nums">
                      {new Date(r.expirationDate).toLocaleDateString("en-PH", { dateStyle: "medium" })}
                    </span>
                    <span
                      className={`inline-block rounded-[2px] px-1.5 py-0.5 text-meta first-letter:uppercase ${
                        r.status === "valid"
                          ? "bg-hema-tint text-hema font-semibold"
                          : r.status === "expiring_soon"
                            ? "bg-eosin-tint text-eosin font-semibold"
                            : r.status === "in_renewal"
                              ? "border border-dashed border-ink-2 text-ink-2 font-medium"
                              : "bg-danger-tint text-danger font-semibold"
                      }`}
                    >
                      {r.status.replace("_", " ")}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Sheet>

      {modalRecord !== null && (
        <ImmigrationModal
          record={modalRecord === "new" ? null : modalRecord}
          onClose={() => setModalRecord(null)}
        />
      )}
    </>
  );
}
