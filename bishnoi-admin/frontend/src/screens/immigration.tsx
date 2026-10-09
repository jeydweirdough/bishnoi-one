"use client";

import { useState } from "react";
import { toast } from "sonner";
import { deleteImmigration } from "@/src/actions/executive";
import { ExportButton, ImportButton } from "@/src/components/sheet-actions";
import { ImmigrationModal } from "@/src/components/executive-modals";
import { DueCell, NameCell, RecordTable, Tag } from "@/src/components/record-table";
import type { ImmigrationRecord } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { Icon } from "@/src/platform/ui/icons";
import { PageHeader } from "@/src/platform/ui/sheet";

/** What this person's role lets them do here; the API checks the same. */
type Can = { create: boolean; edit: boolean; delete: boolean };
const ALL: Can = { create: true, edit: true, delete: true };

const TYPES: Record<string, string> = { acr_card: "ACR I-Card", aep_permit: "DOLE AEP", visa: "9(g) visa", passport: "Passport", exec_id: "Company ID" };
const STATUS: Record<string, string> = { valid: "Valid", expiring_soon: "Expiring soon", in_renewal: "Renewal filed", expired: "Expired" };

function standing(r: ImmigrationRecord): { text: string; tone: "good" | "warn" | "bad" | "info" } {
  if ((r.daysRemaining ?? 0) < 0) return { text: "Expired", tone: "bad" };
  if (r.status === "in_renewal") return { text: "Renewal filed", tone: "info" };
  if ((r.daysRemaining ?? 999) <= 60) return { text: "Due soon", tone: "warn" };
  return { text: "Valid", tone: "good" };
}

/** Expatriates' documents, as the CRM's list: one row per document, the person first. */
export function ImmigrationScreen({ records, canImport = false, can = ALL }: { records: ImmigrationRecord[]; canImport?: boolean; can?: Can }) {
  const [gone, setGone] = useState<string[]>([]);
  const [modal, setModal] = useState<ImmigrationRecord | null | "new">(null);
  const rows = records.filter((r) => !gone.includes(r.id));
  const people = new Set(rows.map((r) => r.individualName)).size;

  return (
    <>
      <PageHeader
        title="Expatriates"
        actions={
          <>
            <ExportButton kind="expatriates" />
            {canImport && <ImportButton href="/immigration/import" />}
            {can.create && (
              <Button variant="primary" onClick={() => setModal("new")}>
                <Icon name="immigration" className="size-4" />
                New expatriate document
              </Button>
            )}
          </>
        }
      >
        {rows.length} documents for {people} {people === 1 ? "person" : "people"} · ACR I-Cards, DOLE work permits, 9(g) visas and passports
      </PageHeader>

      <RecordTable
        rows={rows}
        searchLabel={`Search ${rows.length} documents`}
        search={(r) => [r.individualName, r.designation, r.nationality, r.documentNumber, r.assignedAssistant].join(" ")}
        filter={{ label: "Document", options: { acr_card: "ACR I-Cards", aep_permit: "DOLE AEP", visa: "Visas", passport: "Passports" }, matches: (r, key) => r.documentType === key }}
        emptyIcon="immigration"
        empty={{ title: "No expatriate documents yet", body: can.create ? "Add the first one, or import them from a spreadsheet." : "They appear here once they're added." }}
        rowTone={(r) => ((r.daysRemaining ?? 0) < 0 ? "bad" : null)}
        columns={[
          {
            key: "name",
            label: "Person",
            render: (r) => (
              <NameCell
                name={r.individualName}
                sub={[r.designation, r.nationality].filter(Boolean).join(" · ")}
                filled={(r.daysRemaining ?? 999) <= 60}
                what="document"
                onEdit={can.edit ? () => setModal(r) : undefined}
                onDelete={
                  can.delete
                    ? async () => {
                        const res = await deleteImmigration(r.id);
                        if (!res.ok) {
                          toast.error(res.error);
                          return false;
                        }
                        setGone((g) => [...g, r.id]);
                        toast.success("Document deleted", { description: r.individualName });
                      }
                    : undefined
                }
              />
            ),
          },
          { key: "doc", label: "Document", render: (r) => <span className="block">{TYPES[r.documentType] ?? r.documentType}<span className="block text-[12.5px] text-ink-3">{r.documentNumber}</span></span> },
          { key: "sponsor", label: "Sponsored by", kind: "hide-sm", render: (r) => r.sponsoringEntity || <span className="text-ink-3">—</span> },
          { key: "expires", label: "Expires", render: (r) => <DueCell date={r.expirationDate} days={r.daysRemaining} note={STATUS[r.status]} /> },
          { key: "status", label: "Status", render: (r) => <Tag tone={standing(r).tone} dot>{standing(r).text}</Tag> },
        ]}
      />

      {modal !== null && <ImmigrationModal record={modal === "new" ? null : modal} onClose={() => setModal(null)} />}
    </>
  );
}
