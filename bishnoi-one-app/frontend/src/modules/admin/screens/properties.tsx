"use client";

import { useState } from "react";
import { toast } from "sonner";
import { deleteProperty } from "@/src/modules/admin/actions/executive";
import { ExportButton, ImportButton } from "@/src/modules/admin/components/sheet-actions";
import { PropertyModal } from "@/src/modules/admin/components/executive-modals";
import { DueCell, NameCell, RecordTable, Tag } from "@/src/modules/admin/components/record-table";
import type { PropertyRecord } from "@/src/modules/admin/platform/lib/types";
import { Button } from "@/src/modules/admin/platform/ui/button";
import { Icon } from "@/src/modules/admin/platform/ui/icons";
import { PageHeader } from "@/src/modules/admin/platform/ui/sheet";

/** What this person's role lets them do here; the API checks the same. */
type Can = { create: boolean; edit: boolean; delete: boolean };
const ALL: Can = { create: true, edit: true, delete: true };

const TYPES: Record<string, string> = { office: "Office", warehouse: "Warehouse", depot: "Depot", parking: "Parking", expat_housing: "Staff residence" };
const peso = (n: number | null) => (n == null ? null : `₱${n.toLocaleString("en-PH", { maximumFractionDigits: 0 })}`);
/** The sidebar's red count on Properties: leases not ended with no rent written down. */
const noRent = (p: PropertyRecord) => p.monthlyRent === null && p.status !== "terminated";

function standing(p: PropertyRecord): { text: string; tone: "good" | "warn" | "bad" | "mute" } {
  if (p.status === "terminated") return { text: "Ended", tone: "mute" };
  if ((p.daysRemaining ?? 0) < 0) return { text: "Lease ended", tone: "bad" };
  if ((p.daysRemaining ?? 999) <= 90) return { text: "Renewal due", tone: "warn" };
  return { text: "Current", tone: "good" };
}

/** Offices, warehouses and depots, as the CRM's list. */
export function PropertiesScreen({ properties, canImport = false, can = ALL }: { properties: PropertyRecord[]; canImport?: boolean; can?: Can }) {
  const [gone, setGone] = useState<string[]>([]);
  const [modal, setModal] = useState<PropertyRecord | null | "new">(null);
  const rows = properties.filter((p) => !gone.includes(p.id));
  const missing = rows.filter(noRent).length;

  return (
    <>
      <PageHeader
        title="Properties"
        actions={
          <>
            <ExportButton kind="properties" />
            {canImport && <ImportButton href="/admin/properties/import" />}
            {can.create && (
              <Button variant="primary" onClick={() => setModal("new")}>
                <Icon name="properties" className="size-4" />
                New property
              </Button>
            )}
          </>
        }
      >
        {rows.length} properties · offices, warehouses and depots, with lease end dates, rent and utility accounts
        {missing > 0 && (
          <span className="mt-1 block font-medium text-danger">
            {missing} {missing === 1 ? "property has" : "properties have"} no monthly rent. Pick &quot;No rent&quot; below to see {missing === 1 ? "it" : "them"}.
          </span>
        )}
      </PageHeader>

      <RecordTable
        rows={rows}
        searchLabel={`Search ${rows.length} properties`}
        search={(p) => [p.name, p.address, p.lessorName, p.assignedManager, p.utilitiesInfo].join(" ")}
        filter={{
          label: "Show",
          options: { office: "Offices", warehouse: "Warehouses", depot: "Depots", norent: "No rent" },
          matches: (p, key) => (key === "norent" ? noRent(p) : p.propertyType === key),
        }}
        emptyIcon="properties"
        empty={{ title: "No properties yet", body: can.create ? "Add the first property, or import them from a spreadsheet." : "They appear here once they're added." }}
        rowTone={(p) => ((p.daysRemaining ?? 0) < 0 && p.status !== "terminated" ? "bad" : null)}
        columns={[
          {
            key: "name",
            label: "Property",
            render: (p) => (
              <NameCell
                name={p.name}
                sub={p.address}
                filled={standing(p).tone === "warn" || standing(p).tone === "bad"}
                what="property"
                onEdit={can.edit ? () => setModal(p) : undefined}
                onDelete={
                  can.delete
                    ? async () => {
                        const r = await deleteProperty(p.id);
                        if (!r.ok) {
                          toast.error(r.error);
                          return false;
                        }
                        setGone((g) => [...g, p.id]);
                        toast.success("Property deleted", { description: p.name });
                      }
                    : undefined
                }
              />
            ),
          },
          { key: "type", label: "Type", kind: "hide-sm", render: (p) => <Tag>{TYPES[p.propertyType] ?? p.propertyType}</Tag> },
          { key: "lessor", label: "Lessor", kind: "hide-sm", render: (p) => <span className="block">{p.lessorName}{p.lessorContact && <span className="block text-[12.5px] text-ink-3">{p.lessorContact}</span>}</span> },
          { key: "ends", label: "Lease ends", render: (p) => <DueCell date={p.leaseEnd} days={p.daysRemaining} note={p.noticeDeadlineDays ? `${p.noticeDeadlineDays} days' notice` : undefined} /> },
          { key: "rent", label: "A month", kind: "num", render: (p) => peso(p.monthlyRent) ?? <span className="font-medium text-danger">Not set</span> },
          { key: "status", label: "Status", render: (p) => <Tag tone={standing(p).tone} dot>{standing(p).text}</Tag> },
        ]}
      />

      {modal !== null && <PropertyModal property={modal === "new" ? null : modal} onClose={() => setModal(null)} />}
    </>
  );
}
