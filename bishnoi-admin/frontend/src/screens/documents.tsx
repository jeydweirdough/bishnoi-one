"use client";

import { useState } from "react";
import { toast } from "sonner";
import { deleteDocument } from "@/src/actions/executive";
import { ExportButton, ImportButton } from "@/src/components/sheet-actions";
import { DocumentModal } from "@/src/components/executive-modals";
import { DueCell, NameCell, RecordTable, Tag } from "@/src/components/record-table";
import type { CorporateDocument } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { Icon } from "@/src/platform/ui/icons";
import { PageHeader } from "@/src/platform/ui/sheet";

/** What this person's role lets them do here; the API checks the same. */
type Can = { create: boolean; edit: boolean; delete: boolean };
const ALL: Can = { create: true, edit: true, delete: true };

const CATEGORIES: Record<string, string> = { insurance: "Insurance", commercial_contract: "Contract", nda: "NDA", board_resolution: "Board resolution", legal_retainer: "Legal retainer" };
const STATUS: Record<string, string> = { active: "Active", in_review: "In review", renewed: "Renewed", terminated: "Terminated" };
const peso = (n: number | null) => (n == null ? null : `₱${n.toLocaleString("en-PH", { maximumFractionDigits: 0 })}`);

/** A document with no expiry date and no automatic renewal can't raise a renewal alert. */
const noExpiry = (d: CorporateDocument) => d.expirationDate === null && !d.autoRenews && d.status !== "terminated";

function standing(d: CorporateDocument): { text: string; tone: "good" | "warn" | "bad" | "info" | "mute" } {
  if (d.status === "terminated") return { text: "Terminated", tone: "mute" };
  if (noExpiry(d)) return { text: "No expiry date", tone: "warn" };
  if (d.expirationDate && (d.daysRemaining ?? 0) < 0) return { text: "Expired", tone: "bad" };
  if (d.expirationDate && (d.daysRemaining ?? 999) <= 60) return { text: "Due soon", tone: "warn" };
  if (d.status === "in_review") return { text: "In review", tone: "info" };
  return { text: d.autoRenews ? "Renews itself" : "Current", tone: "good" };
}

/** Contracts, insurance and other corporate documents, as the CRM's list. */
export function DocumentsScreen({ documents, canImport = false, can = ALL }: { documents: CorporateDocument[]; canImport?: boolean; can?: Can }) {
  const [gone, setGone] = useState<string[]>([]);
  const [modal, setModal] = useState<CorporateDocument | null | "new">(null);
  const rows = documents.filter((d) => !gone.includes(d.id));
  const missing = rows.filter(noExpiry).length;

  return (
    <>
      <PageHeader
        title="Documents"
        actions={
          <>
            <ExportButton kind="documents" />
            {canImport && <ImportButton href="/documents/import" />}
            {can.create && (
              <Button variant="primary" onClick={() => setModal("new")}>
                <Icon name="documents" className="size-4" />
                New document
              </Button>
            )}
          </>
        }
      >
        {rows.length} documents · contracts, insurance, NDAs, board resolutions and retainers
        {missing > 0 && (
          <span className="mt-1 block font-medium text-[#8a5a00]">
            {missing} {missing === 1 ? "document has" : "documents have"} no expiry date, so no renewal alert can be sent. Pick &quot;No expiry date&quot; below to see {missing === 1 ? "it" : "them"}.
          </span>
        )}
      </PageHeader>

      <RecordTable
        rows={rows}
        searchLabel={`Search ${rows.length} documents`}
        search={(d) => [d.title, d.counterparty, d.referenceNumber, d.custodian].join(" ")}
        filter={{
          label: "Show",
          options: { insurance: "Insurance", commercial_contract: "Contracts", nda: "NDAs", none: "No expiry date" },
          matches: (d, key) => (key === "none" ? noExpiry(d) : d.category === key),
        }}
        emptyIcon="documents"
        empty={{ title: "No documents yet", body: can.create ? "Add the first document, or import them from a spreadsheet." : "They appear here once they're added." }}
        rowTone={(d) => (d.expirationDate && (d.daysRemaining ?? 0) < 0 && d.status !== "terminated" ? "bad" : null)}
        columns={[
          {
            key: "name",
            label: "Document",
            render: (d) => (
              <NameCell
                name={d.title}
                sub={[d.referenceNumber, d.custodian].filter(Boolean).join(" · ")}
                filled={standing(d).tone === "warn" || standing(d).tone === "bad"}
                what="document"
                onEdit={can.edit ? () => setModal(d) : undefined}
                onDelete={
                  can.delete
                    ? async () => {
                        const r = await deleteDocument(d.id);
                        if (!r.ok) {
                          toast.error(r.error);
                          return false;
                        }
                        setGone((g) => [...g, d.id]);
                        toast.success("Document deleted", { description: d.title });
                      }
                    : undefined
                }
              />
            ),
          },
          { key: "with", label: "With", kind: "hide-sm", render: (d) => d.counterparty },
          { key: "type", label: "Type", kind: "hide-sm", render: (d) => <Tag>{CATEGORIES[d.category] ?? d.category}</Tag> },
          { key: "expires", label: "Expires", render: (d) => (d.expirationDate ? <DueCell date={d.expirationDate} days={d.daysRemaining} note={STATUS[d.status]} /> : <span className="text-ink-3">{d.autoRenews ? "Renews itself" : "No date"}</span>) },
          { key: "value", label: "A year", kind: "num", render: (d) => peso(d.annualValue) ?? <span className="text-ink-3">—</span> },
          { key: "status", label: "Status", render: (d) => <Tag tone={standing(d).tone} dot>{standing(d).text}</Tag> },
        ]}
      />

      {modal !== null && <DocumentModal document={modal === "new" ? null : modal} onClose={() => setModal(null)} />}
    </>
  );
}
