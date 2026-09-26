"use client";

import { useState } from "react";
import { deleteImmigration } from "@/src/actions/executive";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { ImmigrationModal } from "@/src/components/executive-modals";
import type { ImmigrationRecord } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Figure } from "@/src/platform/ui/figure";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

export function ImmigrationScreen({ records: initialRecords }: { records: ImmigrationRecord[] }) {
  const [records, setRecords] = useState<ImmigrationRecord[]>(initialRecords);
  const [selectedType, setSelectedType] = useState<string>("all");
  const [modalRecord, setModalRecord] = useState<ImmigrationRecord | null | "new">(null);

  const types = [
    { key: "all", label: "All Expat Credentials" },
    { key: "acr_card", label: "ACR I-Card" },
    { key: "aep_permit", label: "DOLE AEP" },
    { key: "visa", label: "9(g) Visas" },
    { key: "passport", label: "Passports" },
    { key: "exec_id", label: "Executive IDs" },
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

  const totalCount = records.length;
  const overdueCount = records.filter((r) => (r.daysRemaining ?? 100) < 0).length;
  const expiringCount = records.filter((r) => {
    const d = r.daysRemaining ?? 100;
    return d >= 0 && d <= 30;
  }).length;

  return (
    <>
      <PageHeader
        title="Expatriate & Immigration Compliance"
        crumbs={[{ href: "/", label: "Executive Admin" }, { href: "/immigration", label: "Expatriate & Visas" }]}
        actions={
          <Button variant="primary" onClick={() => setModalRecord("new")}>
            <Icon name="immigration" className="mr-1.5 size-4" />
            Record Expatriate Document
          </Button>
        }
      >
        Manage Bureau of Immigration Alien Certificates of Registration (ACR I-Card), DOLE Alien Employment Permits (AEP), 9(g) visas, and passports.
      </PageHeader>

      {/* Top Figure KPI Metrics Strip */}
      <Sheet className="mb-5 grid divide-y divide-rule sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <Figure label="Expatriate Personnel Registered" value={totalCount} />
        <Figure label="Overdue Visas & Work Permits" value={overdueCount} flag={overdueCount > 0} />
        <Figure label="Expiring within 30 Days" value={expiringCount} flag={expiringCount > 0} />
      </Sheet>

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
          <Empty title="No expatriate records in this category" icon="immigration">
            Record Alien Certificates of Registration (ACR), DOLE work permits, or expat executive passports.
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
                      <span className="text-meta text-ink-2">· {r.designation}</span>
                      <span className="rounded-[2px] border border-rule px-1.5 py-0.2 text-stamp font-medium text-ink-3 uppercase">
                        {r.nationality}
                      </span>
                    </div>

                    <p className="mt-0.5 text-meta text-ink-3">
                      <span className="font-semibold text-ink-2">{docTypeLabel(r.documentType)}</span>:{" "}
                      <span className="font-mono text-ink-2">{r.documentNumber}</span>
                      {r.sponsoringEntity && <> · Sponsor: <span className="text-ink-2">{r.sponsoringEntity}</span></>}
                      {r.assignedAssistant && <> · Assistant: <span className="text-ink-2">{r.assignedAssistant}</span></>}
                      {r.notes && <> · <span className="italic">{r.notes}</span></>}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 shrink-0">
                  <div className="text-right">
                    <span className="block text-meta font-medium text-ink tabular-nums">
                      {new Date(r.expirationDate).toLocaleDateString("en-PH", { dateStyle: "medium" })}
                    </span>
                    <span
                      className={`inline-flex items-center rounded-[2px] px-1.5 py-0.5 text-stamp uppercase ${
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

                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setModalRecord(r)}
                      className="rounded-[3px] border border-rule-strong bg-sheet px-2.5 py-1 text-meta font-medium text-ink hover:border-control"
                    >
                      Edit
                    </button>
                    <ConfirmButton
                      label="Delete"
                      title="Delete Expatriate Record?"
                      body={`Are you sure you want to delete ${r.individualName}'s ${docTypeLabel(r.documentType)} record?`}
                      confirmLabel="Delete Record"
                      danger
                      triggerVariant="quiet"
                      triggerSize="sm"
                      onConfirm={async () => {
                        await deleteImmigration(r.id);
                        setRecords((prev) => prev.filter((item) => item.id !== r.id));
                      }}
                    />
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
