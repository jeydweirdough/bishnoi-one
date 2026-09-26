"use client";

import { useState } from "react";
import { deleteProperty } from "@/src/actions/executive";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { PropertyModal } from "@/src/components/executive-modals";
import type { PropertyRecord } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Figure } from "@/src/platform/ui/figure";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

export function PropertiesScreen({ properties: initialProperties }: { properties: PropertyRecord[] }) {
  const [properties, setProperties] = useState<PropertyRecord[]>(initialProperties);
  const [selectedType, setSelectedType] = useState<string>("all");
  const [modalProperty, setModalProperty] = useState<PropertyRecord | null | "new">(null);

  const types = [
    { key: "all", label: "All Real Estate" },
    { key: "office", label: "Offices & Branches" },
    { key: "warehouse", label: "Central Warehouses" },
    { key: "depot", label: "Regional Depots" },
    { key: "parking", label: "Parking" },
  ];

  const filtered = properties.filter(
    (p) => selectedType === "all" || p.propertyType === selectedType
  );

  const totalCount = properties.length;
  const expiringCount = properties.filter((p) => {
    const d = p.daysRemaining ?? 100;
    return d <= 90;
  }).length;
  const totalMonthlyCommitment = properties.reduce((acc, curr) => acc + (curr.monthlyRent ?? 0), 0);

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

      {/* Top Figure KPI Metrics Strip */}
      <Sheet className="mb-5 grid divide-y divide-rule sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <Figure label="Total Properties & Leases" value={totalCount} />
        <Figure label="Leases Expiring in 90 Days" value={expiringCount} flag={expiringCount > 0} />
        <div className="min-w-0 px-5 py-4">
          <span className="block text-figure text-ink tabular-nums">
            PHP {totalMonthlyCommitment.toLocaleString("en-PH", { maximumFractionDigits: 0 })}
          </span>
          <span className="mt-0.5 block text-meta text-ink-3">Total Monthly Lease Commitment</span>
        </div>
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
          <Empty title="No properties found in this category" icon="properties">
            Record corporate head offices, pharmaceutical distribution warehouses, or regional depots.
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
                      <span className="rounded-[2px] border border-rule px-1.5 py-0.2 text-stamp font-medium text-ink-3 uppercase">
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

                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setModalProperty(pr)}
                      className="rounded-[3px] border border-rule-strong bg-sheet px-2.5 py-1 text-meta font-medium text-ink hover:border-control"
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
                        setProperties((prev) => prev.filter((item) => item.id !== pr.id));
                      }}
                    />
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
