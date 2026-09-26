"use client";

import { useState } from "react";
import { deleteProperty } from "@/src/actions/executive";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { PropertyModal } from "@/src/components/executive-modals";
import type { PropertyRecord } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

export function PropertiesScreen({ properties: initialProperties }: { properties: PropertyRecord[] }) {
  const [properties, setProperties] = useState<PropertyRecord[]>(initialProperties);
  const [selectedType, setSelectedType] = useState<string>("all");
  const [modalProperty, setModalProperty] = useState<PropertyRecord | null | "new">(null);

  const types = [
    { key: "all", label: "All Properties" },
    { key: "office", label: "Offices & Branches" },
    { key: "warehouse", label: "Central Pharma Warehouses" },
    { key: "depot", label: "Regional Depots" },
    { key: "parking", label: "Parking Spaces" },
  ];

  const filtered = initialProperties.filter(
    (p) => selectedType === "all" || p.propertyType === selectedType
  );

  return (
    <>
      <PageHeader
        title="Corporate Real Estate, Leases & Utilities"
        crumbs={[{ href: "/", label: "Executive Admin" }, { href: "/properties", label: "Properties" }]}
        actions={
          <Button variant="primary" onClick={() => setModalProperty("new")}>
            <Icon name="properties" className="mr-1.5 size-4" />
            Record Property / Lease
          </Button>
        }
      >
        Corporate headquarters, warehouse spaces, lease expiration countdowns, rental escalations, utility meters & building dues.
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
          <Empty title="No properties found in this category" icon="properties">
            Record corporate head offices, pharmaceutical distribution warehouses, or regional depots.
          </Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-rule bg-bench/60 text-caps text-ink-3 uppercase">
                <tr>
                  <th className="px-4 py-3 font-semibold">Property & Address</th>
                  <th className="px-4 py-3 font-semibold">Type</th>
                  <th className="px-4 py-3 font-semibold">Lessor / Contact</th>
                  <th className="px-4 py-3 font-semibold">Lease End & Countdown</th>
                  <th className="px-4 py-3 font-semibold">Monthly Rent & Escalation</th>
                  <th className="px-4 py-3 font-semibold">Notice Required</th>
                  <th className="px-4 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {filtered.map((pr) => (
                  <tr key={pr.id} className="transition-colors hover:bg-bench/20">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-ink">{pr.name}</div>
                      <div className="text-meta text-ink-3 line-clamp-1">{pr.address}</div>
                      {pr.utilitiesInfo && (
                        <div className="mt-1 text-meta text-ink-3 font-mono line-clamp-1">
                          {pr.utilitiesInfo}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center rounded-[2px] border border-rule px-2 py-0.5 text-stamp font-semibold text-ink-2 uppercase">
                        {pr.propertyType}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-ink-2">
                      <div className="font-medium text-ink">{pr.lessorName}</div>
                      {pr.lessorContact && <div className="text-meta text-ink-3">{pr.lessorContact}</div>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <CountdownBadge daysRemaining={pr.daysRemaining} urgencyTier={pr.urgencyTier} />
                        <span className="text-meta text-ink-3">
                          {new Date(pr.leaseEnd).toLocaleDateString("en-PH", { dateStyle: "medium" })}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-medium text-ink">
                      {pr.monthlyRent
                        ? `PHP ${pr.monthlyRent.toLocaleString("en-PH", { minimumFractionDigits: 2 })}`
                        : "—"}
                      {pr.escalationRatePct && (
                        <div className="text-meta text-ink-3 font-normal">+{pr.escalationRatePct}% / year</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-meta text-ink-2">
                      <span className="font-semibold text-ink">{pr.noticeDeadlineDays} days</span> before expiry
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => setModalProperty(pr)}
                          className="rounded-[2px] px-2 py-1 text-meta font-medium text-hema hover:bg-hema-tint"
                        >
                          Edit
                        </button>
                        <ConfirmButton
                          label="Delete"
                          title="Delete Property Record?"
                          body={`Are you sure you want to delete ${pr.name}?`}
                          confirmLabel="Delete Property"
                          danger
                          triggerVariant="quiet"
                          triggerSize="sm"
                          onConfirm={async () => {
                            await deleteProperty(pr.id);
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

      {modalProperty !== null && (
        <PropertyModal
          property={modalProperty === "new" ? null : modalProperty}
          onClose={() => setModalProperty(null)}
        />
      )}
    </>
  );
}
