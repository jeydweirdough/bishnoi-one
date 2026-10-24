"use client";

import { useState } from "react";
import { toast } from "sonner";
import { deletePermit } from "@/src/modules/admin/actions/executive";
import { ExportButton, ImportButton } from "@/src/modules/admin/components/sheet-actions";
import { PermitModal } from "@/src/modules/admin/components/executive-modals";
import { DueCell, NameCell, RecordTable, Tag } from "@/src/modules/admin/components/record-table";
import type { ComplianceRecord } from "@/src/modules/admin/platform/lib/types";
import { Button } from "@/src/modules/admin/platform/ui/button";
import { Icon } from "@/src/modules/admin/platform/ui/icons";
import { PageHeader } from "@/src/modules/admin/platform/ui/sheet";

/** What this person's role lets them do here; the API checks the same. */
type Can = { create: boolean; edit: boolean; delete: boolean };
const ALL: Can = { create: true, edit: true, delete: true };

const CATEGORIES: Record<string, string> = { boc: "BOC CPRS", lgu: "Mayor's permit", sec: "SEC GIS", bir: "BIR", fda: "FDA", sanitary_fire: "Fire and sanitary" };
const STATUS: Record<string, string> = { active: "Active", pending_renewal: "For renewal", under_review: "Under agency review", expired: "Expired" };

/** Where a permit stands, in one tag: its countdown first, then its status. */
function standing(p: ComplianceRecord): { text: string; tone: "good" | "warn" | "bad" | "info" } {
  if ((p.daysRemaining ?? 0) < 0) return { text: "Overdue", tone: "bad" };
  if ((p.daysRemaining ?? 999) <= 30) return { text: "Due soon", tone: "warn" };
  if (p.status === "under_review") return { text: "Under agency review", tone: "info" };
  return { text: "Current", tone: "good" };
}

/** Permits, as the CRM's list: the table, the name changes it, a switch by agency. */
export function PermitsScreen({ permits, canImport = false, can = ALL }: { permits: ComplianceRecord[]; canImport?: boolean; can?: Can }) {
  const [gone, setGone] = useState<string[]>([]);
  const [modal, setModal] = useState<ComplianceRecord | null | "new">(null);
  const rows = permits.filter((p) => !gone.includes(p.id));

  return (
    <>
      <PageHeader
        title="Permits"
        actions={
          <>
            <ExportButton kind="permits" />
            {canImport && <ImportButton href="/admin/permits/import" />}
            {can.create && (
              <Button variant="primary" onClick={() => setModal("new")}>
                <Icon name="permits" className="size-4" />
                New permit
              </Button>
            )}
          </>
        }
      >
        {rows.length} permits · BOC, Mayor&apos;s permit, SEC, BIR, FDA, fire and sanitary
      </PageHeader>

      <RecordTable
        rows={rows}
        searchLabel={`Search ${rows.length} permits`}
        search={(p) => [p.title, p.agency, p.referenceNumber, p.responsiblePerson].join(" ")}
        filter={{ label: "Agency", options: CATEGORIES, matches: (p, key) => p.category === key }}
        emptyIcon="permits"
        empty={{ title: "No permits yet", body: can.create ? "Add the first permit, or import them from a spreadsheet." : "They appear here once they're added." }}
        rowTone={(p) => ((p.daysRemaining ?? 0) < 0 ? "bad" : null)}
        columns={[
          {
            key: "name",
            label: "Permit",
            render: (p) => (
              <NameCell
                name={p.title}
                sub={`${p.referenceNumber}${p.responsiblePerson ? ` · ${p.responsiblePerson}` : ""}`}
                filled={(p.daysRemaining ?? 999) <= 30}
                what="permit"
                onEdit={can.edit ? () => setModal(p) : undefined}
                onDelete={
                  can.delete
                    ? async () => {
                        const r = await deletePermit(p.id);
                        if (!r.ok) {
                          toast.error(r.error);
                          return false;
                        }
                        setGone((g) => [...g, p.id]);
                        toast.success("Permit deleted", { description: p.title });
                      }
                    : undefined
                }
              />
            ),
          },
          { key: "agency", label: "Agency", kind: "hide-sm", render: (p) => p.agency },
          { key: "type", label: "Type", kind: "hide-sm", render: (p) => <Tag>{CATEGORIES[p.category] ?? p.category}</Tag> },
          { key: "expires", label: "Expires", render: (p) => <DueCell date={p.expirationDate} days={p.daysRemaining} note={STATUS[p.status]} /> },
          { key: "status", label: "Status", render: (p) => <Tag tone={standing(p).tone} dot>{standing(p).text}</Tag> },
        ]}
      />

      {modal !== null && <PermitModal permit={modal === "new" ? null : modal} onClose={() => setModal(null)} />}
    </>
  );
}
