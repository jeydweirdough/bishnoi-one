"use client";

import { useState } from "react";
import { deleteTicket } from "@/src/actions/executive";
import { CountdownBadge } from "@/src/components/countdown-badge";
import { TicketModal, TicketUpdateModal } from "@/src/components/executive-modals";
import type { OfficeTicket } from "@/src/platform/lib/types";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Icon } from "@/src/platform/ui/icons";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

export function TicketsScreen({ tickets: initialTickets }: { tickets: OfficeTicket[] }) {
  const [tickets, setTickets] = useState<OfficeTicket[]>(initialTickets);
  const [selectedStatus, setSelectedStatus] = useState<string>("active");
  const [modalTicket, setModalTicket] = useState<OfficeTicket | null | "new">(null);
  const [updateModalTicket, setUpdateModalTicket] = useState<OfficeTicket | null>(null);
  const [expandedTicketId, setExpandedTicketId] = useState<string | null>(null);

  const statuses = [
    { key: "active", label: "Active Concerns" },
    { key: "open", label: "Open" },
    { key: "in_progress", label: "In Progress" },
    { key: "pending_vendor", label: "Pending Vendor" },
    { key: "resolved", label: "Resolved / Closed" },
    { key: "all", label: "All Tickets" },
  ];

  const filtered = initialTickets.filter((t) => {
    if (selectedStatus === "active") {
      return ["open", "in_progress", "pending_vendor"].includes(t.status);
    }
    if (selectedStatus === "resolved") {
      return ["resolved", "closed"].includes(t.status);
    }
    if (selectedStatus === "all") return true;
    return t.status === selectedStatus;
  });

  const priorityColor = (p: OfficeTicket["priority"]) => {
    switch (p) {
      case "urgent":
        return "bg-danger-tint text-danger font-bold";
      case "high":
        return "bg-eosin-tint text-eosin font-semibold";
      case "normal":
        return "bg-hema-tint text-hema font-medium";
      default:
        return "border border-rule text-ink-3";
    }
  };

  return (
    <>
      <PageHeader
        title="Office Concerns & Executive Service Desk"
        crumbs={[{ href: "/", label: "Executive Admin" }, { href: "/tickets", label: "Office Concerns" }]}
        actions={
          <Button variant="primary" onClick={() => setModalTicket("new")}>
            <Icon name="tickets" className="mr-1.5 size-4" />
            Raise Office Concern / Request
          </Button>
        }
      >
        Track administrative tasks, facilities repair, executive VIP transport & protocol, office supplies procurement, and urgent courier dispatch.
      </PageHeader>

      {/* Filter Tabs */}
      <div className="mb-4 flex flex-wrap items-center gap-1.5 border-b border-rule pb-2">
        {statuses.map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => setSelectedStatus(s.key)}
            className={`rounded-[2px] px-3 py-1 text-meta font-medium transition-colors ${
              selectedStatus === s.key
                ? "bg-hema text-white"
                : "text-ink-2 hover:bg-bench hover:text-ink"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      <Sheet className="overflow-hidden">
        {filtered.length === 0 ? (
          <Empty title="No office concerns found" icon="tickets">
            All administrative and executive office requests are cleared.
          </Empty>
        ) : (
          <div className="divide-y divide-rule">
            {filtered.map((t) => (
              <div key={t.id} className="p-4 transition-colors hover:bg-bench/20">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-meta font-bold text-ink-3">{t.ticketNumber}</span>
                      <span className={`inline-flex items-center rounded-[2px] px-1.5 py-0.5 text-stamp uppercase ${priorityColor(t.priority)}`}>
                        {t.priority}
                      </span>
                      <span className="inline-flex items-center rounded-[2px] border border-rule px-1.5 py-0.5 text-stamp uppercase text-ink-2">
                        {t.category.replace("_", " ")}
                      </span>
                      <span className="inline-flex items-center rounded-[2px] bg-bench px-1.5 py-0.5 text-stamp uppercase text-ink-2">
                        {t.status.replace("_", " ")}
                      </span>
                    </div>

                    <h3 className="mt-1 text-base font-semibold text-ink">{t.title}</h3>
                    <p className="mt-1 text-sm text-ink-2">{t.description}</p>

                    <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-meta text-ink-3">
                      <span>Requester: <strong className="font-medium text-ink">{t.requesterName}</strong></span>
                      {t.executiveSponsor && (
                        <span>Sponsor: <strong className="font-medium text-ink">{t.executiveSponsor}</strong></span>
                      )}
                      <span>Assigned: <strong className="font-medium text-ink">{t.assignedTo || "Unassigned"}</strong></span>
                      {t.slaDueDate && (
                        <div className="flex items-center gap-1.5">
                          <span>SLA Target:</span>
                          <CountdownBadge daysRemaining={t.daysRemaining} urgencyTier={t.urgencyTier} compact />
                          <span>({new Date(t.slaDueDate).toLocaleDateString("en-PH", { dateStyle: "medium" })})</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                    <button
                      type="button"
                      onClick={() => setUpdateModalTicket(t)}
                      className="rounded-[2px] bg-hema-tint px-2.5 py-1 text-meta font-semibold text-hema hover:bg-hema/15"
                    >
                      Post Action / Note
                    </button>
                    <button
                      type="button"
                      onClick={() => setModalTicket(t)}
                      className="rounded-[2px] px-2 py-1 text-meta font-medium text-ink-2 hover:bg-bench"
                    >
                      Edit
                    </button>
                    <ConfirmButton
                      label="Delete"
                      title="Delete Ticket?"
                      body={`Are you sure you want to delete ${t.ticketNumber}?`}
                      confirmLabel="Delete Ticket"
                      danger
                      triggerVariant="quiet"
                      triggerSize="sm"
                      onConfirm={async () => {
                        await deleteTicket(t.id);
                      }}
                    />
                  </div>
                </div>

                {/* Resolution Notes or Timeline updates */}
                {t.resolutionNotes && (
                  <div className="mt-3 rounded-[2px] bg-bench/70 p-2.5 text-meta text-ink-2">
                    <span className="font-semibold text-ink">Resolution Notes: </span>
                    {t.resolutionNotes}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Sheet>

      {modalTicket !== null && (
        <TicketModal
          ticket={modalTicket === "new" ? null : modalTicket}
          onClose={() => setModalTicket(null)}
        />
      )}

      {updateModalTicket !== null && (
        <TicketUpdateModal
          ticket={updateModalTicket}
          onClose={() => setUpdateModalTicket(null)}
        />
      )}
    </>
  );
}
