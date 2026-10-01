"use client";

import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { deleteProperty } from "@/src/actions/executive";
import { ExportButton, ImportButton } from "@/src/components/sheet-actions";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { PropertyModal } from "@/src/components/executive-modals";
import type { PropertyRecord } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { HealthStrip, healthOf } from "@/src/components/overview-charts";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

/** What this person's role lets them do here; the API checks the same. */
type Can = { create: boolean; edit: boolean; delete: boolean };
const ALL: Can = { create: true, edit: true, delete: true };

export function PropertiesScreen({ properties: initialProperties, canImport = false, can = ALL }: { properties: PropertyRecord[]; canImport?: boolean; can?: Can }) {
  const [properties, setProperties] = useState<PropertyRecord[]>(initialProperties);
  const [selectedType, setSelectedType] = useState<string>("all");
  // The sidebar's red count on Properties: leases not ended with no rent written down.
  const [onlyNoRent, setOnlyNoRent] = useState(false);
  const noRent = properties.filter((p) => p.monthlyRent === null && p.status !== "terminated");
  const [modalProperty, setModalProperty] = useState<PropertyRecord | null | "new">(null);

  const types = [
    { key: "all", label: "All" },
    { key: "office", label: "Offices" },
    { key: "warehouse", label: "Warehouses" },
    { key: "depot", label: "Depots" },
    { key: "parking", label: "Parking" },
  ];

  const filtered = (onlyNoRent ? noRent : properties).filter(
    (p) => selectedType === "all" || p.propertyType === selectedType
  );

  return (
    <>
      <PageHeader
        title="Properties"
        actions={
          <>
            <ExportButton kind="properties" />
            {canImport && <ImportButton href="/properties/import" />}
            {can.create && (
              <Button variant="primary" onClick={() => setModalProperty("new")}>
                <Icon name="properties" className="mr-1.5 size-4" />
                New property
              </Button>
            )}
          </>
        }
      >
        Offices, warehouses and depots the company leases or owns, with lease end dates, rent and utility accounts.
        {(noRent.length > 0 || onlyNoRent) && (
          <span className="mt-1 block text-danger">
            {onlyNoRent ? "Showing the properties with no monthly rent." : `${noRent.length} ${noRent.length === 1 ? "property has" : "properties have"} no monthly rent.`}{" "}
            <button type="button" onClick={() => setOnlyNoRent(!onlyNoRent)} className="font-semibold underline">
              {onlyNoRent ? "Show every property" : `Show ${noRent.length === 1 ? "it" : "them"}`}
            </button>
          </span>
        )}
      </PageHeader>

      <HealthStrip label="leases" {...healthOf(properties.map((pr) => pr.daysRemaining), 90)} />

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
          <Empty title="No properties here" icon="properties">
            Choose another category, or add a property.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {filtered.map((pr) => (
              <li
                key={pr.id}
                className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 py-3.5 transition-colors hover:bg-bench/40"
              >
                <div className="flex min-w-0 flex-1 items-start gap-3">
                  <div className="mt-0.5 shrink-0">
                    <CountdownBadge daysRemaining={pr.daysRemaining} urgencyTier={pr.urgencyTier} />
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-semibold text-sm text-ink">{pr.name}</span>
                      {/* Edit and delete sit with the record they act on. */}
                      <span className="inline-flex items-center">
                        {can.edit && (
                          <button
                            type="button"
                            onClick={() => setModalProperty(pr)}
                            aria-label="Edit property"
                            title="Edit property"
                            className="inline-flex size-7 items-center justify-center rounded-[3px] text-ink-3 hover:bg-hema-tint hover:text-hema"
                          >
                            <Pencil className="size-3.5" aria-hidden />
                          </button>
                        )}
                        {can.delete && (
                          <ConfirmButton
                            label={<span className="sr-only">Delete property</span>}
                            icon={<Trash2 className="size-3.5" aria-hidden />}
                            triggerTitle="Delete property"
                            triggerClassName="!size-7 !px-0 !text-ink-3 hover:!bg-danger/10 hover:!text-danger"
                                                  title={`Delete ${pr.name}?`}
                            body="This property and its lease alerts are deleted. This cannot be undone."
                            confirmLabel="Delete property"
                            danger
                            triggerVariant="quiet"
                            triggerSize="sm"
                            onConfirm={async () => {
                            await deleteProperty(pr.id);
                            setProperties((prev) => prev.filter((item) => item.id !== pr.id));
                            }}
                            
                          />
                        )}
                      </span>
                      <span className="inline-block rounded-[2px] border border-rule px-1.5 py-0.2 text-meta font-medium text-ink-3 first-letter:uppercase">
                        {pr.propertyType}
                      </span>
                    </div>

                    <p className="mt-0.5 text-meta text-ink-3">
                      {pr.address} · Lessor: <span className="font-medium text-ink-2">{pr.lessorName}</span>
                      {pr.lessorContact && <> ({pr.lessorContact})</>}
                      {pr.noticeDeadlineDays && <> · Notice deadline: <span className="font-medium text-ink-2">{pr.noticeDeadlineDays}d prior</span></>}
                      {pr.utilitiesInfo && <> · Meter/Acc: <span className="font-mono text-ink-2">{pr.utilitiesInfo}</span></>}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 shrink-0">
                  <div className="text-right">
                    <span className="block text-meta font-semibold text-ink tabular-nums">
                      {pr.monthlyRent ? `PHP ${pr.monthlyRent.toLocaleString("en-PH", { minimumFractionDigits: 2 })}/mo` : "—"}
                    </span>
                    <span className="block text-stamp text-ink-3">
                      Lease ends {new Date(pr.leaseEnd).toLocaleDateString("en-PH", { dateStyle: "medium" })}
                      {pr.escalationRatePct ? ` · +${pr.escalationRatePct}% esc.` : ""}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Sheet>

      {modalProperty !== null && (
        <PropertyModal
          property={modalProperty === "new" ? null : modalProperty}
          onClose={() => setModalProperty(null)}
        />
      )}
    </>
  );
}
