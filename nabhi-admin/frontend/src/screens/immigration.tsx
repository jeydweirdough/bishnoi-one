"use client";

import { useState } from "react";
import { deleteImmigration } from "@/src/actions/executive";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { ImmigrationModal } from "@/src/components/executive-modals";
import type { ImmigrationRecord } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

export function ImmigrationScreen({ records: initialRecords }: { records: ImmigrationRecord[] }) {
  const [records, setRecords] = useState<ImmigrationRecord[]>(initialRecords);
  const [selectedType, setSelectedType] = useState<string>("all");
  const [modalRecord, setModalRecord] = useState<ImmigrationRecord | null | "new">(null);

  const types = [
    { key: "all", label: "All Expat Documents" },
    { key: "acr_card", label: "ACR I-Card (BI)" },
    { key: "aep_permit", label: "DOLE AEP" },
    { key: "visa", label: "Visas (9g / 47a2)" },
    { key: "passport", label: "Passports" },
    { key: "exec_id", label: "Executive IDs" },
  ];

  const filtered = initialRecords.filter(
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

      {/* Filter Tabs */}
      <div className="mb-4 flex flex-wrap items-center gap-1.5 border-b border-rule pb-2">
        {types.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setSelectedType(t.key)}
            className={`rounded-[2px] px-3 py-1 text-meta font-medium transition-colors ${
              selectedType === t.key
                ? "bg-hema text-white"
                : "text-ink-2 hover:bg-bench hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <Sheet className="overflow-hidden">
        {filtered.length === 0 ? (
          <Empty title="No expatriate records in this category" icon="immigration">
            Record Alien Certificates of Registration (ACR), DOLE work permits, or expat executive passports.
          </Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-rule bg-bench/60 text-caps text-ink-3 uppercase">
                <tr>
                  <th className="px-4 py-3 font-semibold">Expatriate / Executive</th>
                  <th className="px-4 py-3 font-semibold">Nationality</th>
                  <th className="px-4 py-3 font-semibold">Document Type</th>
                  <th className="px-4 py-3 font-semibold">Card / Document #</th>
                  <th className="px-4 py-3 font-semibold">Expiration & Countdown</th>
                  <th className="px-4 py-3 font-semibold">Assigned Assistant</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {filtered.map((r) => (
                  <tr key={r.id} className="transition-colors hover:bg-bench/20">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-ink">{r.individualName}</div>
                      <div className="text-meta text-ink-3">{r.designation}</div>
                    </td>
                    <td className="px-4 py-3 text-ink-2">{r.nationality}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center rounded-[2px] border border-rule px-2 py-0.5 text-stamp font-semibold text-ink-2 uppercase">
                        {docTypeLabel(r.documentType)}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-meta text-ink-2">{r.documentNumber}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <CountdownBadge daysRemaining={r.daysRemaining} urgencyTier={r.urgencyTier} />
                        <span className="text-meta text-ink-3">
                          {new Date(r.expirationDate).toLocaleDateString("en-PH", { dateStyle: "medium" })}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-meta text-ink-2">{r.assignedAssistant || "—"}</td>
                    <td className="px-4 py-3">
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
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => setModalRecord(r)}
                          className="rounded-[2px] px-2 py-1 text-meta font-medium text-hema hover:bg-hema-tint"
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

      {modalRecord !== null && (
        <ImmigrationModal
          record={modalRecord === "new" ? null : modalRecord}
          onClose={() => setModalRecord(null)}
        />
      )}
    </>
  );
}
